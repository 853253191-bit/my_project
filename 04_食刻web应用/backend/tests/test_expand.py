# -*- coding: utf-8 -*-
"""扩召回测试。

目的：极严苛条件下仍能返回结果，验证动态扩召回生效。
预期：items 非空，且 recall_level 为 2 或 3。
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
@pytest.mark.expand
def test_expand_recall_strict_time(api_client):
    """严苛场景：5 分钟做好的佛跳墙 → 仍有结果且带 recall_level。"""
    resp, data = api_client.recommend(
        "5分钟做好的佛跳墙",
        filters={"estimated_time_max": 5},
        top_k=3,
    )
    assert resp.status_code == 200, data
    items = data.get("items") or []
    assert items, f"扩召回失败，结果为空: {data}"

    level = data.get("recall_level")
    assert level is not None, f"缺少 recall_level 字段: {data}"
    assert int(level) in (2, 3), (
        f"期望 recall_level 为 2 或 3（扩召回/兜底），实际={level} count={len(items)}"
    )
