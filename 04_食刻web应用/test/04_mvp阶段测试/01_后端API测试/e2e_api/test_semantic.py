# -*- coding: utf-8 -*-
"""语义检索测试。

目的：验证自然语言查询能召回语义相关菜谱，且系统不崩溃。
预期：汤类/食材类查询有关键词命中；情绪类查询至少有结果。
"""

from __future__ import annotations

import pytest


def _text_blob(item: dict) -> str:
    parts = [
        str(item.get("title") or ""),
        str(item.get("decision_summary") or ""),
        str(item.get("reason") or ""),
        " ".join(str(x) for x in (item.get("ingredients") or [])),
    ]
    return " ".join(parts)


@pytest.mark.full
@pytest.mark.semantic
def test_semantic_soup(api_client):
    """场景 A：想喝热汤 → 至少一道含「汤」或「暖胃」。"""
    resp, data = api_client.recommend(
        "今天好累，想喝点热汤",
        filters={},
        top_k=3,
    )
    assert resp.status_code == 200, data
    items = data.get("items") or []
    assert items, f"汤类检索无结果: {data}"
    hit = any(
        ("汤" in _text_blob(it)) or ("暖胃" in _text_blob(it))
        for it in items
    )
    assert hit, f"未命中汤/暖胃相关结果: {[it.get('title') for it in items]}"


@pytest.mark.full
@pytest.mark.semantic
def test_semantic_ingredients_egg_tomato(api_client):
    """场景 B：冰箱有鸡蛋和番茄 → 至少一道含「番茄」或「蛋」。"""
    resp, data = api_client.recommend(
        "冰箱有鸡蛋和番茄",
        filters={},
        top_k=3,
    )
    assert resp.status_code == 200, data
    items = data.get("items") or []
    assert items, f"食材检索无结果: {data}"
    hit = any(
        ("番茄" in _text_blob(it)) or ("蛋" in _text_blob(it))
        for it in items
    )
    assert hit, f"未命中番茄/蛋相关结果: {[it.get('title') for it in items]}"


@pytest.mark.full
@pytest.mark.semantic
def test_semantic_mood_celebrate(api_client):
    """场景 C：心情很好想庆祝 → 结果不为空（不要求具体菜名）。"""
    resp, data = api_client.recommend(
        "今天心情很好，想庆祝一下",
        filters={},
        top_k=3,
    )
    assert resp.status_code == 200, data
    items = data.get("items") or []
    assert items, f"情绪检索无结果（系统应至少返回菜）: {data}"
