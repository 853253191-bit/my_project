# -*- coding: utf-8 -*-
"""爬虫 CLI 入口。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "src"))

from crawler.base import JsonRecipeStore
from crawler.douguo import DouguoCrawler
from crawler.meishichina import MeishichinaCrawler
from shike.config import resolve_path, load_config


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="爬取豆果美食 / 美食天下菜谱")
    parser.add_argument(
        "--site",
        choices=["douguo", "meishichina", "all"],
        default="all",
        help="目标站点",
    )
    parser.add_argument("--max", type=int, default=100, help="最大采集条数（每个站点）")
    parser.add_argument("--delay", type=float, default=1.0, help="请求间隔（秒）")
    parser.add_argument("--output", type=str, default="", help="输出 JSON 路径")
    parser.add_argument("--headless", action="store_true", help="美食天下无头模式（详情页可能失败）")
    parser.add_argument("--browser", type=str, default="msedge", help="浏览器通道：msedge/chrome/chromium")
    parser.add_argument("--workers", type=int, default=8, help="美食天下并行 worker 数（建议 3~8）")
    parser.add_argument(
        "--category-pages",
        type=int,
        default=1,
        help="每个分类最多翻页数（默认 1=不深翻，直接抓各分类首页）",
    )
    parser.add_argument(
        "--from-urls",
        type=str,
        default="",
        help="美食天下：直接从 URL 列表文件抓详情，跳过列表翻页",
    )
    parser.add_argument("--pages", type=int, default=10, help="每个关键词搜索页数（豆果，每页约20条）")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)

    config = load_config()
    raw_dir = resolve_path(config.data.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    total_added = 0

    if args.site in ("douguo", "all"):
        out = Path(args.output) if args.output and args.site == "douguo" else raw_dir / "douguo_recipes.json"
        store = JsonRecipeStore(out)
        crawler = DouguoCrawler(delay=args.delay)
        try:
            added = crawler.crawl(store, max_recipes=args.max, max_pages_per_keyword=args.pages)
            total_added += added
            print(f"豆果美食: 新增 {added} 条，合计 {len(store)} 条 -> {out}")
        finally:
            crawler.close()

    if args.site in ("meishichina", "all"):
        out = (
            Path(args.output)
            if args.output and args.site == "meishichina"
            else raw_dir / "meishichina_recipes.json"
        )
        store = JsonRecipeStore(out)
        crawler = MeishichinaCrawler(
            delay=max(args.delay, 1.5),
            headless=args.headless,
            browser_channel=args.browser,
            workers=args.workers,
            max_pages_per_category=args.category_pages,
        )
        from_urls = Path(args.from_urls) if args.from_urls else None
        added = crawler.crawl(
            store,
            max_recipes=args.max,
            urls_file=raw_dir / "meishichina_urls.json",
            from_urls=from_urls,
        )
        total_added += added
        print(f"美食天下: 新增 {added} 条，合计 {len(store)} 条 -> {out}")

    print(f"爬取完成，共新增 {total_added} 条")
    print("导入数据库: python -m pipeline.import_data --dir data/raw")


if __name__ == "__main__":
    main()
