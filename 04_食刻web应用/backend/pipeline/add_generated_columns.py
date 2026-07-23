# -*- coding: utf-8 -*-
"""为 recipes 表增加 STORED 生成列，平铺 ai_tags 高频字段并建索引。

说明:
  SQLite 不允许用 ALTER TABLE 直接添加 STORED 生成列（仅 VIRTUAL 可以），
  因此本脚本通过「重建表」方式写入 STORED 列，保证物理存储 + 可建索引。

依赖: 仅 Python 标准库 sqlite3（SQLite ≥ 3.31）。

运行前请手动备份数据库，例如:
  copy data\\sqlite\\recipes.db data\\sqlite\\recipes.db.bak

用法:
  cd backend
  python -m pipeline.add_generated_columns
  python -m pipeline.add_generated_columns --db data/sqlite/recipes.db
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "sqlite" / "recipes.db"

# 注意: recipes 已有业务列 difficulty（爬虫难度文案），故 AI 难度使用 ai_difficulty
GENERATED_COLUMNS: list[tuple[str, str, str]] = [
    # (列名, 类型, GENERATED 表达式)
    (
        "greasiness",
        "INTEGER",
        "json_extract(ai_tags, '$.sensory.greasiness')",
    ),
    (
        "ai_difficulty",
        "TEXT",
        "json_extract(ai_tags, '$.logistics.difficulty')",
    ),
    (
        "spicy_level",
        "INTEGER",
        "json_extract(ai_tags, '$.sensory.spicy_level')",
    ),
    (
        "cuisine_main",
        "TEXT",
        "json_extract(ai_tags, '$.meta.cuisine[0]')",
    ),
    (
        "estimated_time",
        "INTEGER",
        "json_extract(ai_tags, '$.logistics.estimated_time_minutes')",
    ),
    (
        "decision_summary",
        "TEXT",
        "json_extract(ai_tags, '$.decision_summary')",
    ),
    # 数组 -> 逗号分隔字符串，便于 LIKE 查询
    # ["花生","海鲜"] -> 花生,海鲜
    (
        "allergens_str",
        "TEXT",
        "replace(replace(replace(json_extract(ai_tags, '$.health.allergens'), '\"', ''), '[', ''), ']', '')",
    ),
    (
        "diet_labels_str",
        "TEXT",
        "replace(replace(replace(json_extract(ai_tags, '$.health.diet_labels'), '\"', ''), '[', ''), ']', '')",
    ),
]

INDEXES: list[tuple[str, str]] = [
    ("idx_greasiness", "greasiness"),
    ("idx_ai_difficulty", "ai_difficulty"),
    ("idx_spicy", "spicy_level"),
    ("idx_cuisine", "cuisine_main"),
    ("idx_time", "estimated_time"),
    ("idx_allergens_str", "allergens_str"),
    ("idx_diet_labels_str", "diet_labels_str"),
]

logger = logging.getLogger("add_generated_columns")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_sqlite_version(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2].split("-")[0]) if len(parts) > 2 else 0
    return major, minor, patch


def check_sqlite_version() -> None:
    """SQLite < 3.31 不支持 GENERATED COLUMN，直接退出。"""
    ver = sqlite3.sqlite_version
    major, minor, patch = parse_sqlite_version(ver)
    logger.info("当前 SQLite 版本: %s", ver)
    if (major, minor, patch) < (3, 31, 0):
        raise SystemExit(
            f"当前 SQLite 版本 {ver} < 3.31，不支持 GENERATED COLUMN。\n"
            "请升级 SQLite，或自行建物理平铺表 recipes_flat。"
        )


def get_table_xinfo(conn: sqlite3.Connection, table: str = "recipes") -> list[sqlite3.Row]:
    """返回含 hidden 标记的列信息（生成列为 hidden=2/3）。"""
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(f"PRAGMA table_xinfo({table})").fetchall())
    except sqlite3.OperationalError:
        # 极老版本无 table_xinfo
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return rows


def get_existing_columns(conn: sqlite3.Connection, table: str = "recipes") -> set[str]:
    """包含生成列（优先 table_xinfo，因 table_info 不返回 GENERATED 列）。"""
    try:
        rows = conn.execute(f"PRAGMA table_xinfo({table})").fetchall()
        # xinfo: cid, name, type, notnull, dflt_value, pk, hidden
        return {r[1] for r in rows}
    except sqlite3.OperationalError:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}


def get_base_column_defs(
    conn: sqlite3.Connection, table: str = "recipes"
) -> tuple[list[str], list[str]]:
    """取出非生成列的建表片段与列名（用于重建表）。"""
    xinfo = get_table_xinfo(conn, table)
    defs: list[tuple[str, str, int]] = []

    for r in xinfo:
        name = r["name"] if isinstance(r, sqlite3.Row) else r[1]
        if isinstance(r, sqlite3.Row):
            keys = r.keys()
            hidden = int(r["hidden"] or 0) if "hidden" in keys else 0
            col_type = (r["type"] or "TEXT").strip() or "TEXT"
            notnull = int(r["notnull"] or 0)
            dflt = r["dflt_value"]
            pk = int(r["pk"] or 0)
        else:
            hidden = 0
            col_type = (r[2] or "TEXT").strip() or "TEXT"
            notnull = int(r[3] or 0)
            dflt = r[4]
            pk = int(r[5] or 0)

        if hidden >= 2:
            continue

        parts = [f'"{name}" {col_type}']
        if notnull:
            parts.append("NOT NULL")
        if dflt is not None:
            parts.append(f"DEFAULT {dflt}")
        defs.append((name, " ".join(parts), pk))

    pk_ranks = [d[2] for d in defs if d[2] > 0]
    single_pk = len(pk_ranks) == 1 and pk_ranks[0] == 1

    col_sql: list[str] = []
    for name, frag, pk in defs:
        if single_pk and pk == 1:
            col_sql.append(f"{frag} PRIMARY KEY")
        else:
            col_sql.append(frag)

    if not single_pk and pk_ranks:
        ordered = sorted(((d[2], d[0]) for d in defs if d[2] > 0), key=lambda x: x[0])
        quoted = ", ".join(f'"{name}"' for _, name in ordered)
        col_sql.append(f"PRIMARY KEY ({quoted})")

    return col_sql, [d[0] for d in defs]


def missing_generated_columns(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    existing = get_existing_columns(conn)
    return [c for c in GENERATED_COLUMNS if c[0] not in existing]


def rebuild_table_with_stored_columns(
    conn: sqlite3.Connection,
    to_add: list[tuple[str, str, str]],
) -> None:
    """重建 recipes 表以添加 STORED 生成列。"""
    logger.info("SQLite 不支持 ALTER 添加 STORED 列，开始重建表 ...")
    base_defs, base_names = get_base_column_defs(conn, "recipes")

    gen_defs = [
        f'"{name}" {ctype} GENERATED ALWAYS AS ({expr}) STORED'
        for name, ctype, expr in to_add
    ]
    # 若某些生成列已存在，也需要保留它们的定义
    # 简化：只追加本次缺失的；已有的生成列若不在 base 中会丢失
    # 因此把「已存在且是生成列」也一并带上
    existing = get_existing_columns(conn)
    already = [c for c in GENERATED_COLUMNS if c[0] in existing and c[0] not in {x[0] for x in to_add}]
    for name, ctype, expr in already:
        gen_defs.append(
            f'"{name}" {ctype} GENERATED ALWAYS AS ({expr}) STORED'
        )

    create_sql = (
        "CREATE TABLE recipes__new (\n  "
        + ",\n  ".join(base_defs + gen_defs)
        + "\n)"
    )
    logger.info("创建临时表 recipes__new ...")
    conn.execute(create_sql)

    cols_csv = ", ".join(f'"{n}"' for n in base_names)
    logger.info("拷贝数据（%d 列）...", len(base_names))
    conn.execute(
        f"INSERT INTO recipes__new ({cols_csv}) SELECT {cols_csv} FROM recipes"
    )

    # 保留旧表索引名列表（稍后重建业务索引）
    old_indexes = conn.execute(
        """
        SELECT name, sql FROM sqlite_master
        WHERE type='index' AND tbl_name='recipes' AND sql IS NOT NULL
        """
    ).fetchall()

    logger.info("替换原表 ...")
    conn.execute("DROP TABLE recipes")
    conn.execute("ALTER TABLE recipes__new RENAME TO recipes")

    # 恢复原有非自动索引
    for name, sql in old_indexes:
        if name.startswith("sqlite_autoindex_"):
            continue
        # 跳过我们即将新建的索引名，避免冲突
        new_idx_names = {i[0] for i in INDEXES}
        if name in new_idx_names:
            continue
        try:
            conn.execute(sql)
            logger.info("恢复索引: %s", name)
        except sqlite3.OperationalError as exc:
            logger.warning("恢复索引失败 %s: %s", name, exc)

    conn.commit()
    logger.info("表重建完成")


def create_indexes(conn: sqlite3.Connection) -> int:
    """幂等创建索引，返回新建/确认索引数。"""
    existing_cols = get_existing_columns(conn)
    created = 0
    for idx_name, col_name in INDEXES:
        if col_name not in existing_cols:
            logger.warning("列 %s 不存在，跳过索引 %s", col_name, idx_name)
            continue
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {idx_name} ON recipes({col_name})"
        )
        created += 1
        logger.info("索引就绪: %s ON recipes(%s)", idx_name, col_name)
    conn.commit()
    return created


def print_verification(conn: sqlite3.Connection) -> None:
    print("")
    print("========== 验证（前 5 条） ==========")
    print(
        "SQL: SELECT id, title, greasiness, ai_difficulty, cuisine_main "
        "FROM recipes LIMIT 5;"
    )
    rows = conn.execute(
        """
        SELECT id, title, greasiness, ai_difficulty, cuisine_main,
               spicy_level, estimated_time, decision_summary,
               allergens_str, diet_labels_str
        FROM recipes
        WHERE ai_tags IS NOT NULL AND trim(ai_tags) != ''
        LIMIT 5
        """
    ).fetchall()
    for r in rows:
        print(
            f"id={r[0]} | {str(r[1])[:28]} | grease={r[2]} | "
            f"diff={r[3]} | cuisine={r[4]} | spicy={r[5]} | "
            f"time={r[6]} | summary={r[7]} | "
            f"allergens={r[8]!r} | diet={r[9]!r}"
        )
    print("====================================")


def run(db_path: Path) -> None:
    print("⚠️  请确认已手动备份数据库后再继续。")
    print(f"   数据库路径: {db_path}")
    print("   示例: copy data\\sqlite\\recipes.db data\\sqlite\\recipes.db.bak")
    print("")

    check_sqlite_version()

    if not db_path.is_file():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cols = get_existing_columns(conn)
        if "ai_tags" not in cols:
            raise RuntimeError("recipes 表缺少 ai_tags 列，无法创建生成列")

        if "difficulty" in cols:
            logger.info(
                "表中已有业务列 difficulty，AI 难度字段使用 ai_difficulty "
                "（对应 $.logistics.difficulty）"
            )

        to_add = missing_generated_columns(conn)
        added = 0
        if not to_add:
            logger.info("所有目标生成列均已存在，跳过建列")
        else:
            logger.info("待新增生成列: %s", ", ".join(c[0] for c in to_add))
            # 优先尝试 ALTER（对 STORED 会失败，再走重建）
            try:
                for name, ctype, expr in to_add:
                    sql = (
                        f'ALTER TABLE recipes ADD COLUMN "{name}" {ctype} '
                        f"GENERATED ALWAYS AS ({expr}) STORED"
                    )
                    conn.execute(sql)
                    added += 1
                    logger.info("ALTER 添加成功: %s", name)
                conn.commit()
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "stored" in msg or "generated" in msg:
                    conn.rollback()
                    rebuild_table_with_stored_columns(conn, to_add)
                    added = len(to_add)
                else:
                    raise

        indexed = create_indexes(conn)
        print_verification(conn)

        print("")
        print(f"迁移完成，索引已建立。新增生成列: {added}，处理索引: {indexed}")
        print("查询示例:")
        print("  SELECT * FROM recipes WHERE greasiness < 3;")
        print("  SELECT * FROM recipes WHERE ai_difficulty = 'easy';")
        print("  SELECT * FROM recipes WHERE allergens_str NOT LIKE '%花生%';")
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 recipes 增加 ai_tags 平铺生成列")
    parser.add_argument(
        "--db",
        type=str,
        default="",
        help="SQLite 路径（默认 backend/data/sqlite/recipes.db）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = parse_args(argv)
    backend_root = Path(__file__).resolve().parents[1]
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    if not db_path.is_absolute():
        db_path = (backend_root / db_path).resolve()
    run(db_path)


if __name__ == "__main__":
    main()
