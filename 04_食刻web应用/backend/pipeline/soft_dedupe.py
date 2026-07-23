# -*- coding: utf-8 -*-
"""SQLite 菜谱软去重：标题高相似度 + LLM 语义判重。

依赖:
  pip install openai python-dotenv

用法:
  cd backend
  python -m pipeline.soft_dedupe --dry-run
  python -m pipeline.soft_dedupe --limit 200
  python -m pipeline.soft_dedupe --skip-llm
  python -m pipeline.soft_dedupe

环境变量（LLM 判重）:
  OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
  未设置 OPENAI_API_KEY 时自动跳过 LLM 阶段，仅做标题相似度去重。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from pipeline.clean_data import (
    DEFAULT_DB_PATH,
    _delete_by_ids,
    _json_array_len,
    _pick_keeper,
    _record_deletions,
    backup_recipes_table,
    connect_db,
    ensure_deleted_records_table,
    table_count,
)

logger = logging.getLogger("soft_dedupe")

# 标题同义词归一（用于分桶与 LLM 前粗筛）
TITLE_SYNONYMS: dict[str, str] = {
    "西红柿": "番茄",
    "马铃薯": "土豆",
    "地瓜": "红薯",
    "番薯": "红薯",
    "包菜": "卷心菜",
    "圆白菜": "卷心菜",
    "花椰菜": "花菜",
    "菜花": "花菜",
    "青瓜": "黄瓜",
    "胡萝": "胡萝卜",
    "瘦肉": "猪肉",
    "猪瘦肉": "猪肉",
}

# 括号/前缀修饰，软去重时剥离
PAREN_RE = re.compile(r"[（(【\[].*?[）)】\]]")
PREFIXES = (
    "家常",
    "经典",
    "正宗",
    "简易",
    "简单",
    "秘制",
    "懒人",
    "新手",
    "零失败",
    "超简单",
    "妈妈",
)

LLM_SYSTEM = """你是菜谱去重专家。判断两道菜是否本质为同一道菜（仅标题写法/修饰不同，核心菜名与做法一致）。

例如应判为重复：
- 番茄炒蛋 vs 西红柿炒鸡蛋
- 红烧肉（妈妈版） vs 家常红烧肉
- 可乐鸡翅 vs 可乐烧鸡翅

例如不应判为重复：
- 红烧牛肉 vs 清炖牛肉
- 番茄炒蛋 vs 番茄蛋汤
- 宫保鸡丁 vs 鱼香肉丝

只输出 JSON：
{"is_duplicate": true/false, "similarity": 0.0-1.0, "reason": "简短中文理由"}

similarity 表示标题/内容综合相似度（0~1）。仅当 is_duplicate 为 true 且 similarity >= 0.95 才视为重复。"""


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def groups(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for i in range(len(self.parent)):
            out[self.find(i)].append(i)
        return dict(out)


def normalize_title(title: str) -> str:
    """基础规范化：去空白、统一括号内容。"""
    t = re.sub(r"\s+", "", (title or "").strip())
    return t


def normalize_title_core(title: str) -> str:
    """剥离修饰语后的核心菜名，用于分桶。"""
    t = normalize_title(title)
    t = PAREN_RE.sub("", t)
    for p in PREFIXES:
        if t.startswith(p):
            t = t[len(p) :]
    for src, dst in TITLE_SYNONYMS.items():
        t = t.replace(src, dst)
    # 去掉常见尾缀
    for suffix in ("的做法", "教程", "步骤", "recipe"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
    return t


def title_similarity(a: str, b: str) -> float:
    """标题相似度 0~1（基于规范化后的 SequenceMatcher）。"""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # 核心名相似度与全文相似度取较高者
    ca, cb = normalize_title_core(a), normalize_title_core(b)
    sim_full = SequenceMatcher(None, na, nb).ratio()
    sim_core = SequenceMatcher(None, ca, cb).ratio() if ca and cb else 0.0
    return max(sim_full, sim_core)


def parse_ingredient_names(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return []
    names: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                n = str(item.get("name", "")).strip()
            else:
                n = str(item).strip()
            if n:
                names.append(n)
    return names


def ingredient_fingerprint(row: sqlite3.Row) -> str:
    """食材指纹：排序后的前 5 个主料名。"""
    names = parse_ingredient_names(row["ingredients"])
    canon = []
    for n in names[:8]:
        for src, dst in TITLE_SYNONYMS.items():
            n = n.replace(src, dst)
        canon.append(n)
    canon = sorted(set(canon))[:5]
    return "|".join(canon)


def steps_preview(row: sqlite3.Row, max_steps: int = 3) -> str:
    raw = row["steps"]
    if raw is None:
        return ""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return ""
    texts: list[str] = []
    if isinstance(data, list):
        for i, item in enumerate(data[:max_steps]):
            if isinstance(item, dict):
                texts.append(str(item.get("text", "")).strip())
            else:
                texts.append(str(item).strip())
    return "；".join(t for t in texts if t)


def build_llm_user_prompt(row_a: sqlite3.Row, row_b: sqlite3.Row) -> str:
    def brief(r: sqlite3.Row) -> str:
        ings = "、".join(parse_ingredient_names(r["ingredients"])[:6])
        return (
            f"标题: {r['title']}\n"
            f"核心菜名: {normalize_title_core(str(r['title'] or ''))}\n"
            f"食材: {ings or '无'}\n"
            f"步骤数: {_json_array_len(r['steps'])}\n"
            f"步骤摘要: {steps_preview(r)}"
        )

    return f"菜谱 A:\n{brief(row_a)}\n\n菜谱 B:\n{brief(row_b)}"


def create_llm_client() -> tuple[OpenAI, str] | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip() or "qwen-plus"
    if not api_key or not base_url:
        return None
    return OpenAI(api_key=api_key, base_url=base_url), model


def llm_judge_duplicate(
    client: OpenAI,
    model: str,
    row_a: sqlite3.Row,
    row_b: sqlite3.Row,
    threshold: float,
) -> tuple[bool, float, str]:
    """LLM 判重，返回 (是否合并, 相似度, 理由)。"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": LLM_SYSTEM},
            {"role": "user", "content": build_llm_user_prompt(row_a, row_b)},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    is_dup = bool(data.get("is_duplicate", False))
    sim = float(data.get("similarity", 0.0))
    reason = str(data.get("reason", ""))
    merge = is_dup and sim >= threshold
    return merge, sim, reason


def find_string_duplicate_pairs(
    rows: list[sqlite3.Row],
    threshold: float,
) -> list[tuple[int, int, float]]:
    """标题相似度 >= threshold 的配对（分桶加速）。"""
    pairs: list[tuple[int, int, float]] = []
    buckets: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        core = normalize_title_core(str(r["title"] or ""))
        if not core:
            continue
        # 按核心名前 2 字 + 长度分桶
        key = f"{core[:2]}_{len(core)//3}"
        buckets[key].append(i)

    seen: set[tuple[int, int]] = set()
    for indices in buckets.values():
        if len(indices) < 2:
            continue
        for ai in range(len(indices)):
            for bi in range(ai + 1, len(indices)):
                i, j = indices[ai], indices[bi]
                if i > j:
                    i, j = j, i
                if (i, j) in seen:
                    continue
                sim = title_similarity(
                    str(rows[i]["title"] or ""),
                    str(rows[j]["title"] or ""),
                )
                if sim >= threshold:
                    seen.add((i, j))
                    pairs.append((i, j, sim))
    return pairs


def find_llm_candidate_pairs(
    rows: list[sqlite3.Row],
    title_threshold: float,
    llm_min_sim: float,
) -> list[tuple[int, int]]:
    """LLM 候选对：标题相似度在 [llm_min_sim, title_threshold) 或同食材指纹+核心名相近。"""
    candidates: set[tuple[int, int]] = set()
    ing_buckets: dict[str, list[int]] = defaultdict(list)

    for i, r in enumerate(rows):
        fp = ingredient_fingerprint(r)
        if fp:
            ing_buckets[fp].append(i)

    # 同食材指纹桶内两两配对（通常很小）
    for indices in ing_buckets.values():
        if len(indices) < 2 or len(indices) > 30:
            continue
        for ai in range(len(indices)):
            for bi in range(ai + 1, len(indices)):
                i, j = indices[ai], indices[bi]
                if i > j:
                    i, j = j, i
                ta = str(rows[i]["title"] or "")
                tb = str(rows[j]["title"] or "")
                sim = title_similarity(ta, tb)
                if llm_min_sim <= sim < title_threshold:
                    candidates.add((i, j))
                elif normalize_title_core(ta) == normalize_title_core(tb):
                    candidates.add((i, j))

    # 核心菜名相同但全文相似度未达阈值
    core_buckets: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        core = normalize_title_core(str(r["title"] or ""))
        if len(core) >= 3:
            core_buckets[core].append(i)
    for indices in core_buckets.values():
        if len(indices) < 2:
            continue
        for ai in range(len(indices)):
            for bi in range(ai + 1, len(indices)):
                i, j = indices[ai], indices[bi]
                if i > j:
                    i, j = j, i
                sim = title_similarity(
                    str(rows[i]["title"] or ""),
                    str(rows[j]["title"] or ""),
                )
                if sim < title_threshold:
                    candidates.add((i, j))

    return sorted(candidates)


def collect_deletions_from_groups(
    rows: list[sqlite3.Row],
    uf: UnionFind,
) -> tuple[list[sqlite3.Row], list[dict[str, Any]]]:
    """从并查集分组得到待删行与合并日志。"""
    groups = uf.groups()
    to_delete: list[sqlite3.Row] = []
    merge_log: list[dict[str, Any]] = []

    for members in groups.values():
        if len(members) <= 1:
            continue
        group_rows = [rows[i] for i in members]
        keeper = _pick_keeper(group_rows)
        removed = [r for r in group_rows if r["id"] != keeper["id"]]
        to_delete.extend(removed)
        merge_log.append(
            {
                "keeper_id": keeper["id"],
                "keeper_title": keeper["title"],
                "removed": [{"id": r["id"], "title": r["title"]} for r in removed],
            }
        )
    return to_delete, merge_log


def run_soft_dedupe(
    db_path: Path,
    *,
    dry_run: bool = False,
    title_threshold: float = 0.95,
    llm_min_sim: float = 0.45,
    use_llm: bool = True,
    max_llm_pairs: int = 0,
    limit: int = 0,
    verbose: bool = False,
) -> None:
    conn = connect_db(db_path)
    try:
        before = table_count(conn)
        logger.info("软去重前总行数: %d", before)
        logger.info("数据库: %s", db_path)
        if dry_run:
            logger.info("模式: dry-run")

        ensure_deleted_records_table(conn)
        if not dry_run:
            backup_recipes_table(conn)

        sql = "SELECT * FROM recipes ORDER BY rowid ASC"
        params: list[Any] = []
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        rows = list(conn.execute(sql, params).fetchall())
        n = len(rows)
        logger.info("参与去重样本: %d 条", n)

        uf = UnionFind(n)
        string_pairs = find_string_duplicate_pairs(rows, title_threshold)
        for i, j, sim in string_pairs:
            uf.union(i, j)
        logger.info("标题相似度 >= %.2f 自动合并对数: %d", title_threshold, len(string_pairs))

        llm_merged = 0
        llm_checked = 0
        llm_skipped_no_key = False

        if use_llm:
            llm = create_llm_client()
            if llm is None:
                llm_skipped_no_key = True
                logger.warning("未配置 OPENAI_API_KEY/BASE_URL，跳过 LLM 语义判重")
            else:
                client, model = llm
                candidates = find_llm_candidate_pairs(rows, title_threshold, llm_min_sim)
                if max_llm_pairs > 0:
                    candidates = candidates[:max_llm_pairs]
                logger.info("LLM 候选对数: %d（model=%s）", len(candidates), model)

                for idx, (i, j) in enumerate(candidates, start=1):
                    if uf.find(i) == uf.find(j):
                        continue
                    llm_checked += 1
                    ta = str(rows[i]["title"] or "")
                    tb = str(rows[j]["title"] or "")
                    logger.info(
                        "LLM [%d/%d] %s  vs  %s",
                        idx,
                        len(candidates),
                        ta[:30],
                        tb[:30],
                    )
                    try:
                        merge, sim, reason = llm_judge_duplicate(
                            client, model, rows[i], rows[j], title_threshold
                        )
                        if merge:
                            uf.union(i, j)
                            llm_merged += 1
                            logger.info("  -> 合并 similarity=%.2f %s", sim, reason)
                        else:
                            logger.debug("  -> 保留 similarity=%.2f %s", sim, reason)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("  LLM 判重失败: %s", exc)

        to_delete, merge_log = collect_deletions_from_groups(rows, uf)
        dup_groups = sum(1 for g in uf.groups().values() if len(g) > 1)

        _record_deletions(conn, to_delete, "soft_dedupe", dry_run)
        deleted_n = _delete_by_ids(conn, [r["id"] for r in to_delete], dry_run)
        if not dry_run:
            conn.commit()

        after = before - deleted_n if dry_run else table_count(conn)

        # 导出合并日志
        if merge_log and not dry_run:
            out_dir = Path(db_path).parent.parent / "processed"
            out_dir.mkdir(parents=True, exist_ok=True)
            log_path = out_dir / "soft_dedupe_merges.json"
            log_path.write_text(
                json.dumps(merge_log, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("合并日志: %s", log_path)

        print("")
        print("========== 软去重结果 ==========")
        print(f"处理样本数:     {n}")
        print(f"去重前总行数:   {before}")
        print(f"标题高相似合并: {len(string_pairs)} 对（阈值>={title_threshold}）")
        if use_llm and not llm_skipped_no_key:
            print(f"LLM 检查对数:   {llm_checked}")
            print(f"LLM 确认合并:   {llm_merged} 对")
        elif llm_skipped_no_key:
            print("LLM 判重:       已跳过（未配置 API）")
        print(f"重复组数:       {dup_groups}")
        print(f"删除条数:       {deleted_n}")
        print(f"去重后总行数:   {after}")
        if dry_run:
            print("（dry-run：未真正删除）")
        else:
            print("删除明细: deleted_records (reason=soft_dedupe)")
        print("================================")
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQLite 菜谱软去重（标题相似度 + LLM）")
    parser.add_argument("--db", type=str, default="", help="SQLite 路径")
    parser.add_argument(
        "--title-threshold",
        type=float,
        default=0.95,
        help="标题相似度阈值，>= 此值直接合并（默认 0.95）",
    )
    parser.add_argument(
        "--llm-min-sim",
        type=float,
        default=0.45,
        help="LLM 候选对最低标题相似度（默认 0.45）",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="仅标题相似度去重，不调用 LLM",
    )
    parser.add_argument(
        "--max-llm-pairs",
        type=int,
        default=0,
        help="最多 LLM 判重对数（0=不限制，建议先设 50 测试）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="仅对前 N 条记录做去重（0=全库）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不删除")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    project_root = backend_root.parent
    load_dotenv(backend_root / ".env")
    load_dotenv(project_root / ".env")

    args = parse_args(argv)
    setup_logging(args.verbose)

    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    if not db_path.is_absolute():
        db_path = (backend_root / db_path).resolve()

    run_soft_dedupe(
        db_path=db_path,
        dry_run=args.dry_run,
        title_threshold=args.title_threshold,
        llm_min_sim=args.llm_min_sim,
        use_llm=not args.skip_llm,
        max_llm_pairs=args.max_llm_pairs,
        limit=args.limit,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
