# -*- coding: utf-8 -*-
"""按标题模糊相似度删除近似重复菜谱（每组保留一条）。

用法:
  cd backend
  python -m pipeline.delete_fuzzy_dupes --dry-run
  python -m pipeline.delete_fuzzy_dupes
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "src"))
sys.path.insert(0, str(BACKEND_ROOT))

from pipeline.clean_data import (  # noqa: E402
    DEFAULT_DB_PATH,
    _delete_by_ids,
    _pick_keeper,
    _record_deletions,
    backup_recipes_table,
    connect_db,
    ensure_deleted_records_table,
    table_count,
)
from shike.services.title_dedupe import (  # noqa: E402
    FUZZY_DUP_THRESHOLD,
    normalize_title_core,
    title_similarity,
)

logger = logging.getLogger("delete_fuzzy_dupes")


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def groups(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for i in range(len(self.parent)):
            out[self.find(i)].append(i)
        return dict(out)


def build_duplicate_groups(rows: list, threshold: float) -> list[list]:
    n = len(rows)
    uf = UnionFind(n)

    # 核心名完全相同先合并
    core_map: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        core = normalize_title_core(str(r["title"] or ""))
        if core:
            core_map[core].append(i)
    for indices in core_map.values():
        for j in range(1, len(indices)):
            uf.union(indices[0], indices[j])

    # 分桶模糊配对
    buckets: dict[tuple, list[int]] = defaultdict(list)
    cores = [normalize_title_core(str(r["title"] or "")) for r in rows]
    for i, core in enumerate(cores):
        if not core:
            continue
        buckets[(core[0], len(core) // 2)].append(i)

    for indices in buckets.values():
        m = len(indices)
        for a in range(m):
            ia = indices[a]
            ca = cores[ia]
            ta = str(rows[ia]["title"] or "")
            for b in range(a + 1, m):
                ib = indices[b]
                if uf.find(ia) == uf.find(ib):
                    continue
                cb = cores[ib]
                if abs(len(ca) - len(cb)) > 4:
                    continue
                sim = title_similarity(ta, str(rows[ib]["title"] or ""))
                if sim >= threshold:
                    uf.union(ia, ib)

    groups: list[list] = []
    for idxs in uf.groups().values():
        if len(idxs) <= 1:
            continue
        groups.append([rows[i] for i in idxs])
    return groups


def delete_from_chroma(ids: list[str]) -> int:
    """从 Chroma 删除对应 id（失败不阻断 SQLite 删除）。"""
    if not ids:
        return 0
    try:
        import chromadb
        from shike.config import load_config, resolve_path

        cfg = load_config()
        chroma_path = resolve_path(
            os.getenv("CHROMA_PATH", "") or cfg.rag.store_path
        )
        client = chromadb.PersistentClient(path=str(chroma_path))
        col = client.get_or_create_collection(name="recipes")
        # Chroma 批量删除
        batch = 200
        removed = 0
        for i in range(0, len(ids), batch):
            chunk = ids[i : i + batch]
            try:
                col.delete(ids=chunk)
                removed += len(chunk)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Chroma 删除部分失败: %s", exc)
        return removed
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chroma 清理跳过: %s", exc)
        return 0


def run(db_path: Path, threshold: float, dry_run: bool) -> None:
    conn = connect_db(db_path)
    try:
        before = table_count(conn)
        rows = list(conn.execute("SELECT * FROM recipes ORDER BY rowid ASC").fetchall())
        groups = build_duplicate_groups(rows, threshold)

        to_delete = []
        keep_log = []
        for group in groups:
            keeper = _pick_keeper(group)
            keep_log.append((keeper["id"], keeper["title"], len(group)))
            for r in group:
                if r["id"] != keeper["id"]:
                    to_delete.append(r)

        delete_ids = [str(r["id"]) for r in to_delete]
        logger.info(
            "重复组=%s 待删=%s 阈值=%.2f dry_run=%s",
            len(groups),
            len(delete_ids),
            threshold,
            dry_run,
        )
        for kid, title, gsize in keep_log[:12]:
            logger.info("保留组(%s): %s | %s", gsize, kid, title)

        if dry_run:
            print(
                f"dry-run: groups={len(groups)} delete={len(delete_ids)} "
                f"remain~={before - len(delete_ids)}"
            )
            return

        ensure_deleted_records_table(conn)
        backup_recipes_table(conn)
        _record_deletions(conn, to_delete, "fuzzy_title_dedupe", dry_run=False)
        deleted_n = _delete_by_ids(conn, delete_ids, dry_run=False)
        conn.commit()
        after = table_count(conn)
        chroma_n = delete_from_chroma(delete_ids)
        print(
            f"完成: 删除 SQLite {deleted_n} 条，Chroma 尝试删除 {chroma_n} 条，"
            f"{before} -> {after}"
        )
    finally:
        conn.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    load_dotenv(BACKEND_ROOT / ".env")
    load_dotenv(BACKEND_ROOT.parent / ".env")

    parser = argparse.ArgumentParser(description="删除标题模糊重复菜谱")
    parser.add_argument("--db", type=str, default="")
    parser.add_argument(
        "--threshold",
        type=float,
        default=FUZZY_DUP_THRESHOLD,
        help=f"相似度阈值（默认 {FUZZY_DUP_THRESHOLD}）",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    if not db_path.is_absolute():
        db_path = (BACKEND_ROOT / db_path).resolve()
    run(db_path=db_path, threshold=args.threshold, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
