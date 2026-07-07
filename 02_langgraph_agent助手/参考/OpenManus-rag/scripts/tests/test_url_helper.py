# -*- coding: utf-8 -*-
"""URL 帮助工具 smoke test。"""
import sys
from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(CASE_ROOT) not in sys.path:
    sys.path.insert(0, str(CASE_ROOT))

from app.tool.url_helper import URLHelper, build_ctrip_flight_url_from_query


def main():
    helper = URLHelper()

    print("=== 日期解析测试 ===")
    for date_str in ["1月30日", "2月14号", "2026-01-30", "01/30", "明天", "后天"]:
        print(f"  {date_str} -> {helper.parse_date(date_str)}")

    print("\n=== 查询解析与 URL 构建 ===")
    queries = [
        "用携程查询 1月30日 从上海到北京的机票",
        "明天从北京到广州的机票",
        "1月30日从上海到北京的机票",
    ]
    for query in queries:
        url = build_ctrip_flight_url_from_query(query)
        print(f"  查询: {query}")
        print(f"  URL: {url}\n")


if __name__ == "__main__":
    main()
