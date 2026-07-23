# -*- coding: utf-8 -*-
"""食谱数据导入 CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 将 backend 目录加入 path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "src"))
sys.path.insert(0, str(BACKEND_ROOT))

from pipeline.clean import clean_recipes
from pipeline.seed_recipes import generate_seed_recipes
from shike.config import load_config, resolve_path
from shike.db.repository import RecipeRepository


def import_json_file(repo: RecipeRepository, path: Path) -> int:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        data = raw.get("recipes", [raw])
    else:
        data = raw
    cleaned = clean_recipes(data)
    repo.upsert_many(cleaned)
    return len(cleaned)


def import_from_dir(repo: RecipeRepository, directory: Path) -> int:
    total = 0
    for path in sorted(directory.glob("*.json")):
        total += import_json_file(repo, path)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="导入食谱数据到 SQLite")
    parser.add_argument("--seed", action="store_true", help="生成并导入种子数据（默认3000条）")
    parser.add_argument("--count", type=int, default=3000, help="种子数据数量")
    parser.add_argument("--file", type=str, help="导入单个 JSON 文件")
    parser.add_argument("--dir", type=str, help="导入目录下所有 JSON 文件")
    args = parser.parse_args()

    config = load_config()
    db_path = resolve_path(config.data.sqlite_path)
    repo = RecipeRepository(db_path)

    if args.seed:
        recipes = generate_seed_recipes(args.count)
        cleaned = clean_recipes(recipes)
        repo.upsert_many(cleaned)
        processed_dir = resolve_path(config.data.processed_dir)
        processed_dir.mkdir(parents=True, exist_ok=True)
        out_path = processed_dir / "seed_recipes.json"
        out_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"种子数据导入完成: {len(cleaned)} 条 -> {db_path}")
        print(f"已导出: {out_path}")
        return

    if args.file:
        count = import_json_file(repo, Path(args.file))
        print(f"导入完成: {count} 条")
        return

    if args.dir:
        count = import_from_dir(repo, Path(args.dir))
        print(f"导入完成: {count} 条")
        return

    raw_dir = resolve_path(config.data.raw_dir)
    if raw_dir.is_dir():
        json_files = sorted(raw_dir.glob("*.json"))
        # 跳过探测/临时文件
        json_files = [p for p in json_files if not p.name.startswith("_")]
        if json_files:
            total = 0
            for path in json_files:
                total += import_json_file(repo, path)
            print(f"从 raw 目录导入: {total} 条（{len(json_files)} 个文件）")
            return

    parser.print_help()


if __name__ == "__main__":
    main()
