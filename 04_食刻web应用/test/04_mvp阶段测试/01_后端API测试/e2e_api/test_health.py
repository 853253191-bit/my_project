# -*- coding: utf-8 -*-
"""服务健康检查测试。

目的：确认后端、前端首页、今日推荐核心入口可用。
预期：health=ok，首页 HTTP 200，daily 返回 5 条。
"""

from __future__ import annotations

import pytest
import requests


@pytest.mark.smoke
def test_health_ok(api_client):
    """测试 /api/health 返回 status=ok。"""
    resp = api_client.get("/api/health")
    assert resp.status_code == 200, f"health 状态码异常: {resp.status_code}"
    data = resp.json()
    assert data.get("status") == "ok", f"health 响应异常: {data}"
    assert int(data.get("recipe_count") or 0) > 0
    assert int(data.get("chroma_count") or 0) > 0


@pytest.mark.smoke
def test_home_page_reachable(home_url):
    """测试前端首页可访问（HTTP 200）。"""
    resp = requests.get(home_url + "/", timeout=15)
    assert resp.status_code == 200, f"首页不可用: {resp.status_code} url={home_url}/"


@pytest.mark.smoke
def test_daily_recommendations_count(api_client):
    """测试 /api/daily_recommendations 默认返回 5 条。"""
    resp = api_client.get("/api/daily_recommendations", params={"limit": 5})
    assert resp.status_code == 200, f"daily 状态码异常: {resp.status_code}"
    data = resp.json()
    items = data.get("items") or []
    assert len(items) == 5, f"期望 5 条，实际 {len(items)}: {data}"
    assert int(data.get("count") or 0) == 5
