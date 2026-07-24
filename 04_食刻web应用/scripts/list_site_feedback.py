#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 / 整理站点意见反馈（定期后台查看用）。

用法示例：
  python scripts/list_site_feedback.py
  python scripts/list_site_feedback.py --status pending --limit 100
  python scripts/list_site_feedback.py --db /opt/shike/data/sqlite/recipes.db
  python scripts/list_site_feedback.py --mark-reviewed 12
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def default_db() -> Path:
    here = Path(__file__).resolve()
    local = here.parents[1] / "backend" / "data" / "sqlite" / "recipes.db"
    prod = Path("/opt/shike/data/sqlite/recipes.db")
    if prod.exists():
        return prod
    return local


def main() -> int:
    parser = argparse.ArgumentParser(description="列出站点意见反馈")
    parser.add_argument("--db", type=Path, default=None, help="SQLite 路径")
    parser.add_argument("--status", default="pending", help="pending|reviewed|archived|all")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--mark-reviewed",
        type=int,
        default=None,
        metavar="ID",
        help="将指定反馈标记为 reviewed",
    )
    args = parser.parse_args()
    db_path = args.db or default_db()
    if not db_path.exists():
        print(f"数据库不存在: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 确保表存在
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS site_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            contact TEXT,
            category TEXT DEFAULT '建议',
            user_id TEXT,
            username TEXT,
            client_ip TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()

    if args.mark_reviewed is not None:
        cur = conn.execute(
            "UPDATE site_feedback SET status = 'reviewed' WHERE id = ?",
            (args.mark_reviewed,),
        )
        conn.commit()
        print(f"已标记 id={args.mark_reviewed} 为 reviewed，影响行数={cur.rowcount}")
        conn.close()
        return 0

    status = (args.status or "pending").strip().lower()
    if status == "all":
        rows = conn.execute(
            """
            SELECT id, category, status, username, contact, content, created_at
            FROM site_feedback
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, category, status, username, contact, content, created_at
            FROM site_feedback
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (status, args.limit),
        ).fetchall()

    print(f"数据库: {db_path}")
    print(f"共 {len(rows)} 条（status={status}, limit={args.limit}）")
    print("-" * 60)
    for r in rows:
        user = r["username"] or "匿名"
        contact = r["contact"] or "-"
        print(
            f"#{r['id']} [{r['category']}][{r['status']}] "
            f"{r['created_at']} | {user} | {contact}"
        )
        print(r["content"])
        print("-" * 60)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
