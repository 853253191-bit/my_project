# -*- coding: utf-8 -*-
"""SQLite 菜谱数据硬清洗脚本（仅标准库）。

用法:
  cd backend
  python -m pipeline.clean_data
  python -m pipeline.clean_data --dry-run

无需额外依赖（仅使用 Python 标准库 sqlite3）。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 请在此处手动配置本地 SQLite 路径
# ---------------------------------------------------------------------------
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "sqlite" / "recipes.db"

logger = logging.getLogger("clean_data")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def connect_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite 文件不存在: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def table_count(conn: sqlite3.Connection, table: str = "recipes") -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def ensure_deleted_records_table(conn: sqlite3.Connection) -> None:
    """创建删除记录表（若不存在）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deleted_records (
            id TEXT,
            title TEXT,
            reason TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            payload TEXT
        )
        """
    )
    conn.commit()


def backup_recipes_table(conn: sqlite3.Connection) -> str:
    """清洗前备份 recipes 全表到 recipes_backup_时间戳（不 DROP）。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"recipes_backup_{stamp}"
    # 避免同名：若已存在则追加后缀
    existing = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    name = backup_name
    i = 1
    while name in existing:
        name = f"{backup_name}_{i}"
        i += 1

    conn.execute(f"CREATE TABLE {name} AS SELECT * FROM recipes")
    conn.commit()
    n = table_count(conn, name)
    logger.info("已备份 recipes -> %s（%d 条）", name, n)
    return name


def _is_empty_jsonish(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    text = str(value).strip()
    if not text:
        return True
    if text in ("[]", "{}", "null", "None"):
        return True
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    if parsed is None:
        return True
    if isinstance(parsed, (list, dict)) and len(parsed) == 0:
        return True
    return False


def _json_array_len(value: Any) -> int:
    """解析 steps/ingredients 的 JSON 数组长度；解析失败返回 0。"""
    if value is None:
        return 0
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    text = str(value).strip()
    if not text:
        return 0
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return 0
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        return len(parsed)
    return 0


def _record_deletions(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    reason: str,
    dry_run: bool,
) -> None:
    if not rows:
        return
    now = datetime.now(timezone.utc).isoformat()
    payload_rows = []
    for r in rows:
        data = dict(r)
        payload_rows.append(
            (
                data.get("id"),
                data.get("title"),
                reason,
                now,
                json.dumps(data, ensure_ascii=False, default=str),
            )
        )
    if dry_run:
        return
    conn.executemany(
        """
        INSERT INTO deleted_records (id, title, reason, deleted_at, payload)
        VALUES (?, ?, ?, ?, ?)
        """,
        payload_rows,
    )


def _delete_by_ids(
    conn: sqlite3.Connection,
    ids: list[str],
    dry_run: bool,
) -> int:
    if not ids:
        return 0
    if dry_run:
        return len(ids)
    # 分批删除，避免 SQL 过长
    batch = 500
    deleted = 0
    for i in range(0, len(ids), batch):
        chunk = ids[i : i + batch]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.execute(
            f"DELETE FROM recipes WHERE id IN ({placeholders})",
            chunk,
        )
        deleted += cur.rowcount if cur.rowcount is not None else len(chunk)
    return deleted


def step1_delete_empty(conn: sqlite3.Connection, dry_run: bool) -> int:
    """删除空 title / 空 steps / 空 ingredients。"""
    rows = conn.execute("SELECT * FROM recipes").fetchall()
    to_delete: list[sqlite3.Row] = []
    for r in rows:
        title = r["title"]
        title_ok = title is not None and len(str(title).strip()) >= 2
        if not title_ok:
            to_delete.append(r)
            continue
        if _is_empty_jsonish(r["steps"]):
            to_delete.append(r)
            continue
        if _is_empty_jsonish(r["ingredients"]):
            to_delete.append(r)
            continue

    _record_deletions(conn, to_delete, "empty_data", dry_run)
    ids = [r["id"] for r in to_delete]
    n = _delete_by_ids(conn, ids, dry_run)
    if not dry_run:
        conn.commit()
    logger.info("空数据删除: %d", n)
    return n


def step2_delete_junk(conn: sqlite3.Connection, dry_run: bool) -> int:
    """删除乱码/测试占位标题。

    规则：title 长度 < 4，且包含 test / 测试，或标题恰好为「菜谱」。
    """
    rows = conn.execute("SELECT * FROM recipes").fetchall()
    to_delete: list[sqlite3.Row] = []
    for r in rows:
        title = "" if r["title"] is None else str(r["title"]).strip()
        if len(title) >= 4:
            continue
        lower = title.lower()
        is_test = ("test" in lower) or ("测试" in title)
        is_placeholder_recipe = title == "菜谱"
        if is_test or is_placeholder_recipe:
            to_delete.append(r)

    _record_deletions(conn, to_delete, "junk_or_test", dry_run)
    ids = [r["id"] for r in to_delete]
    n = _delete_by_ids(conn, ids, dry_run)
    if not dry_run:
        conn.commit()
    logger.info("乱码/测试删除: %d", n)
    return n


def _pick_keeper(group: list[sqlite3.Row]) -> sqlite3.Row:
    """同名组内保留一条：description 最长 > steps 数组最长 > id 最小。"""

    def desc_len(row: sqlite3.Row) -> int:
        d = row["description"]
        if d is None:
            return 0
        return len(str(d).strip())

    def steps_len(row: sqlite3.Row) -> int:
        return _json_array_len(row["steps"])

    def id_key(row: sqlite3.Row) -> str:
        return "" if row["id"] is None else str(row["id"])

    # 排序：desc 长优先、steps 长优先、id 小优先 → 取第一条
    ranked = sorted(
        group,
        key=lambda r: (-desc_len(r), -steps_len(r), id_key(r)),
    )
    return ranked[0]


def step3_dedupe_by_title(conn: sqlite3.Connection, dry_run: bool) -> int:
    """完全重名去重：同 title 只留一条。"""
    rows = conn.execute("SELECT * FROM recipes").fetchall()
    groups: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        title = "" if r["title"] is None else str(r["title"]).strip()
        # 用规范化后的 title 作为分组键（去多余空白）
        key = re.sub(r"\s+", " ", title)
        groups.setdefault(key, []).append(r)

    to_delete: list[sqlite3.Row] = []
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        keeper = _pick_keeper(group)
        for r in group:
            if r["id"] != keeper["id"]:
                to_delete.append(r)

    _record_deletions(conn, to_delete, "duplicate_title", dry_run)
    ids = [r["id"] for r in to_delete]
    n = _delete_by_ids(conn, ids, dry_run)
    if not dry_run:
        conn.commit()
    logger.info("重复删除: %d（涉及重名组）", n)
    return n


def run_clean(db_path: Path, dry_run: bool = False) -> None:
    conn = connect_db(db_path)
    try:
        before = table_count(conn, "recipes")
        logger.info("清洗前总行数: %d", before)
        logger.info("数据库: %s", db_path)
        if dry_run:
            logger.info("模式: dry-run（不写库、不真正删除）")

        ensure_deleted_records_table(conn)
        if not dry_run:
            backup_recipes_table(conn)

        empty_n = step1_delete_empty(conn, dry_run=dry_run)
        junk_n = step2_delete_junk(conn, dry_run=dry_run)
        dup_n = step3_dedupe_by_title(conn, dry_run=dry_run)

        after = before - empty_n - junk_n - dup_n if dry_run else table_count(conn, "recipes")

        print("")
        print("========== 清洗结果 ==========")
        print(f"清洗前总行数: {before}")
        print(f"空数据删除数: {empty_n}")
        print(f"乱码删除数:   {junk_n}")
        print(f"重复删除数:   {dup_n}")
        print(f"清洗后总行数: {after}")
        print(f"合计删除:     {empty_n + junk_n + dup_n}")
        if dry_run:
            print("（dry-run：以上删除未真正执行）")
        else:
            print("删除明细已写入表: deleted_records")
        print("==============================")
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQLite 菜谱硬清洗")
    parser.add_argument(
        "--db",
        type=str,
        default="",
        help="SQLite 路径（默认使用脚本内 DEFAULT_DB_PATH）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计将要删除的数量，不备份、不删除",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = parse_args(argv)

    backend_root = Path(__file__).resolve().parents[1]
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    if not db_path.is_absolute():
        db_path = (backend_root / db_path).resolve()

    run_clean(db_path=db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
