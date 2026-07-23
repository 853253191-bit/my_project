# -*- coding: utf-8 -*-
"""向量入库 CLI。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "src"))
sys.path.insert(0, str(BACKEND_ROOT))

from shike.config import load_config, resolve_path
from shike.db.repository import RecipeRepository
from shike.rag.ingest import ingest_all


def main() -> None:
    parser = argparse.ArgumentParser(description="将 SQLite 食谱数据向量化入库 Chroma")
    parser.add_argument("--all", action="store_true", help="全量入库")
    args = parser.parse_args()

    config = load_config()
    db_path = resolve_path(config.data.sqlite_path)
    repo = RecipeRepository(db_path)

    count = repo.count()
    if count == 0:
        print("SQLite 中无食谱数据，请先运行: python -m pipeline.import_data --seed")
        sys.exit(1)

    if args.all:
        n = ingest_all(config, repo)
        print(f"向量入库完成: {n} 个 chunk，食谱总数 {count}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
