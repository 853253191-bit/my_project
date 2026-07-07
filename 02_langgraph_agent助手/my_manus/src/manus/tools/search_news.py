# -*- coding: utf-8 -*-
"""Tavily 新闻搜索（SPEC §4.1）。"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from manus.config import config_to_dict
from manus.pipeline.progress import emit_progress


async def search_news(
    query: str,
    config: dict[str, Any] | Any,
    *,
    days: int = 1,
) -> list[dict[str, Any]]:
    cfg = config_to_dict(config)
    search_cfg = cfg.get("search", {})
    provider = search_cfg.get("provider", "tavily")
    api_key = search_cfg.get("api_key") or os.getenv("TAVILY_API_KEY") or os.getenv("API_KEY", "")
    max_results = int(search_cfg.get("max_results", 10))

    if provider != "tavily":
        raise ValueError(f"暂不支持的搜索 provider: {provider}")

    if not api_key:
        emit_progress("未配置 Tavily API Key，使用占位新闻")
        return _placeholder_news(query)

    emit_progress("调用 Tavily 搜索 API…")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results,
                "days": days,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    emit_progress(f"Tavily 返回 {len(data.get('results', []))} 条结果")

    items: list[dict[str, Any]] = []
    for idx, r in enumerate(data.get("results", [])):
        items.append(
            {
                "id": f"news-{uuid4().hex[:8]}",
                "title": r.get("title", ""),
                "summary": r.get("content", "")[:300],
                "source": r.get("source", "Tavily"),
                "url": r.get("url", ""),
                "published_at": r.get("published_date") or datetime.now(timezone.utc).isoformat(),
                "heat_score": max(0.1, 1.0 - idx * 0.1),
                "relevance_tags": ["AI", "hardware"],
                "hardware_focus": True,
                "hardware_tags": [],
                "research_hint": "待 Agent1 细化",
                "why_selected": "Tavily 检索结果",
            }
        )
    return items


def _placeholder_news(query: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "id": f"news-{uuid4().hex[:8]}",
            "title": f"占位新闻: {query[:40]}",
            "summary": "搜索 API 未配置，使用占位数据。请设置 TAVILY_API_KEY。",
            "source": "placeholder",
            "url": "https://example.com/placeholder",
            "published_at": now,
            "heat_score": 0.5,
            "relevance_tags": ["placeholder"],
            "hardware_focus": True,
            "hardware_tags": [],
            "research_hint": "配置 Tavily 后重新运行",
            "why_selected": "占位",
        }
    ]
