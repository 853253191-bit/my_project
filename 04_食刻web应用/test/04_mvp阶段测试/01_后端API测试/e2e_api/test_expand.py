# -*- coding: utf-8 -*-
"""扩召回测试。

目的：极严苛条件下仍能返回结果，验证动态扩召回生效。
预期：items 非空，且 recall_level 为 2 或 3。

说明：生产库中存在大量 estimated_time<=5 的菜，仅用 time_max=5
可能在第 1 级就凑满 top_k。因此叠加「不存在的菜系」迫使严格过滤为 0。
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
@pytest.mark.expand
def test_expand_recall_strict_time(api_client):
    """严苛场景：不可能同时满足的条件 → 触发扩召回/兜底。"""
    resp, data = api_client.recommend(
        "5分钟做好的佛跳墙",
        filters={
            "estimated_time_max": 1,
            # 不存在的菜系：保证第 1 级几乎必为空，随后放宽/去掉菜系或随机兜底
            "cuisine_main": "不存在的测试菜系XYZ",
        },
        top_k=3,
    )
    assert resp.status_code == 200, data
    items = data.get("items") or []
    assert items, f"扩召回失败，结果为空: {data}"

    level = data.get("recall_level")
    assert level is not None, f"缺少 recall_level 字段: {data}"
    assert int(level) in (2, 3), (
        f"期望 recall_level 为 2 或 3（扩召回/兜底），实际={level} "
        f"count={len(items)} titles={[it.get('title') for it in items]}"
    )


@pytest.mark.smoke
@pytest.mark.expand
def test_expand_recall_field_always_present(api_client):
    """兼容场景：普通严苛时间条件下至少有结果，且带 recall_level。"""
    resp, data = api_client.recommend(
        "5分钟做好的佛跳墙",
        filters={"estimated_time_max": 5},
        top_k=3,
    )
    assert resp.status_code == 200, data
    items = data.get("items") or []
    assert items, f"结果不应为空: {data}"
    assert data.get("recall_level") is not None, f"缺少 recall_level: {data}"
    assert int(data["recall_level"]) in (1, 2, 3)
