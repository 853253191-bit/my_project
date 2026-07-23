# -*- coding: utf-8 -*-
"""豆果 API 详情 HTML 中的 JSON 提取。"""

from __future__ import annotations

import json
import re
from typing import Any


def _decode_json_string(val: str) -> str:
    try:
        return json.loads(f'"{val}"')
    except json.JSONDecodeError:
        return val


def parse_douguo_api_html(html: str, recipe_id: int, url: str) -> dict[str, Any] | None:
    """从 api.douguo.net/recipe/detail 返回的 HTML 中提取 JSON 数据。"""
    data: dict[str, Any] = {"_recipe_id": recipe_id, "_source_url": url}

    # 提取 cookstep 数组
    m = re.search(r'"cookstep"\s*:\s*(\[.*?\])\s*,\s*"', html, re.S)
    if m:
        try:
            data["cookstep"] = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    for field, pattern in [
        ("title", r'"title"\s*:\s*"([^"]+)"'),
        ("cookstory", r'"cookstory"\s*:\s*"((?:\\.|[^"\\])*)"'),
        ("tips", r'"tips"\s*:\s*"((?:\\.|[^"\\])*)"'),
        ("image", r'"image"\s*:\s*"(https?://[^"]+)"'),
        ("cook_time", r'"cook_time"\s*:\s*"([^"]*)"'),
        ("cook_difficulty", r'"cook_difficulty"\s*:\s*"([^"]*)"'),
    ]:
        fm = re.search(pattern, html)
        if fm:
            val = _decode_json_string(fm.group(1))
            data[field] = val

    # major / minor 数组
    for field in ("major", "minor"):
        fm = re.search(rf'"{field}"\s*:\s*(\[.*?\])\s*,\s*"', html, re.S)
        if fm:
            try:
                data[field] = json.loads(fm.group(1))
            except json.JSONDecodeError:
                pass

    if not data.get("title") and not data.get("cookstep"):
        return None
    return data
