# -*- coding: utf-8 -*-
"""Agent1：硬件向 Top5 新闻采集。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from manus.schemas.models import NewsItem
from manus.tools.search_news import search_news

_NEWS_DEFAULTS: dict[str, Any] = {
    "summary": "摘要待补充",
    "source": "unknown",
    "url": "https://example.com/news",
    "published_at": datetime.now(timezone.utc).isoformat(),
    "heat_score": 0.5,
    "relevance_tags": ["AI"],
    "hardware_focus": True,
    "hardware_tags": [],
    "research_hint": "待分析",
    "why_selected": "检索入选",
}

# 重点覆盖美股 + A 股 AI 产业链近期新技术与热门方向
_AGENT1_SEARCH_QUERIES = [
    "美股 AI产业链 新技术 应用 热门方向 半导体 算力 CPO HBM 光模块 近期",
    "A股 AI产业链 新技术 热点 先进封装 HBM 存储芯片 IDC 算力 光模块 近期",
    "US stock AI supply chain new technology semiconductor datacenter optical module recent",
]


def _normalize_news(raw: dict[str, Any]) -> NewsItem:
    merged = {**_NEWS_DEFAULTS, **raw}
    if "id" not in merged:
        merged["id"] = f"news-{uuid4().hex[:8]}"
    if merged.get("research_hint") == "待分析":
        merged["research_hint"] = "关注美股/A股 AI产业链新技术与热门应用方向"
    tags = list(merged.get("relevance_tags") or [])
    for tag in ("AI", "hardware", "US-CN"):
        if tag not in tags:
            tags.append(tag)
    merged["relevance_tags"] = tags[:6]
    return NewsItem.model_validate(merged)


def _merge_news_results(items_list: list[list[dict[str, Any]]], top_n: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for batch in items_list:
        for raw in batch:
            key = (raw.get("url") or raw.get("title") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(raw)
    merged.sort(key=lambda x: x.get("heat_score", 0), reverse=True)
    return merged[:top_n]


async def run_agent1(state: dict[str, Any], config: dict[str, Any] | Any) -> dict[str, Any]:
    from manus.pipeline.progress import emit_progress

    wf = config.get("workflow", {}) if isinstance(config, dict) else config["workflow"]
    top_n = int(wf.get("news_top_n", 5))
    emit_progress("检索美股/A股 AI 产业链近期新技术与热门方向…")
    batches: list[list[dict[str, Any]]] = []
    for query in _AGENT1_SEARCH_QUERIES:
        emit_progress(f"Tavily 检索：{query[:48]}…")
        batches.append(await search_news(query, config, days=3))
    raw = _merge_news_results(batches, top_n=max(top_n * 2, 10))[:top_n]
    emit_progress(f"合并去重后筛选 Top {len(raw)} 条")
    items = [_normalize_news(x) for x in raw]
    return {
        "news_items": [i.model_dump(mode="json") for i in items],
        "step_output_summary": f"采集美股/A股 AI产业链热点新闻 {len(items)} 条",
    }
