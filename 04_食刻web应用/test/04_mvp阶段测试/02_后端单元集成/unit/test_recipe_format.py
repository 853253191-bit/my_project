# -*- coding: utf-8 -*-
"""菜谱格式化单元测试。"""

from __future__ import annotations

from shike.services.recipe_format import format_recipe_markdown, ingredient_names


def test_ingredient_names_mixed():
    names = ingredient_names(
        ["鸡蛋", {"name": "番茄"}, {"ingredient": "葱", "amount": "少许"}, "鸡蛋", ""]
    )
    assert names == ["鸡蛋", "番茄", "葱"]


def test_format_recipe_markdown_contains_sections():
    md = format_recipe_markdown(
        {
            "title": "番茄炒蛋",
            "decision_summary": "家常快手",
            "cuisine_main": "家常",
            "estimated_time": 15,
            "ai_difficulty": "easy",
            "ingredients": [{"name": "鸡蛋", "amount": "2", "unit": "个"}],
            "steps": ["打蛋", "下锅翻炒"],
        }
    )
    assert "## 番茄炒蛋" in md
    assert "家常快手" in md
    assert "### 食材" in md
    assert "鸡蛋 2个" in md
    assert "### 步骤" in md or "打蛋" in md
