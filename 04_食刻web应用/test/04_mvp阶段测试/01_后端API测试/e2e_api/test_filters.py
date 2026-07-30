# -*- coding: utf-8 -*-
"""硬过滤功能测试。

目的：验证辣度 / 时间 / 过敏原等 metadata 硬过滤生效。
说明：若触发扩召回（recall_level>=2），过滤可能被放宽，此时跳过严格断言。
"""

from __future__ import annotations

import pytest


def _items(data: dict) -> list:
    return list(data.get("items") or [])


def _strict_or_skip(data: dict) -> None:
    """扩召回兜底结果不做硬过滤严格断言。"""
    level = data.get("recall_level")
    if level is not None and int(level) >= 2:
        pytest.skip(f"扩召回生效 recall_level={level}，跳过严格硬过滤断言")


@pytest.mark.smoke
@pytest.mark.filter
def test_spicy_level_max_zero(api_client):
    """场景 A：spicy_level_max=0 时，结果辣度均为 0。"""
    resp, data = api_client.recommend(
        "随便吃点",
        filters={"spicy_level_max": 0},
        top_k=5,
    )
    assert resp.status_code == 200, data
    items = _items(data)
    assert items, f"辣度过滤无结果: {data}"
    _strict_or_skip(data)
    for item in items:
        level = item.get("spicy_level")
        if level is None:
            continue
        assert int(level) == 0, f"期望不辣，实际 spicy_level={level} title={item.get('title')}"


@pytest.mark.smoke
@pytest.mark.filter
def test_estimated_time_max_15(api_client):
    """场景 B：estimated_time_max=15 时，结果耗时均 <= 15。"""
    resp, data = api_client.recommend(
        "随便吃点",
        filters={"estimated_time_max": 15},
        top_k=5,
    )
    assert resp.status_code == 200, data
    items = _items(data)
    assert items, f"时间过滤无结果: {data}"
    _strict_or_skip(data)
    for item in items:
        t = item.get("estimated_time")
        if t is None:
            continue
        assert int(t) <= 15, f"期望<=15分钟，实际={t} title={item.get('title')}"


@pytest.mark.smoke
@pytest.mark.filter
def test_exclude_allergens_peanut(api_client):
    """场景 C：排除花生后，allergens_str 不含「花生」。"""
    resp, data = api_client.recommend(
        "随便吃点",
        filters={"exclude_allergens": ["花生"]},
        top_k=5,
    )
    assert resp.status_code == 200, data
    items = _items(data)
    assert items, f"过敏原过滤无结果: {data}"
    for item in items:
        allergens = str(item.get("allergens_str") or "")
        assert "花生" not in allergens, (
            f"未排除花生: allergens_str={allergens!r} title={item.get('title')}"
        )
