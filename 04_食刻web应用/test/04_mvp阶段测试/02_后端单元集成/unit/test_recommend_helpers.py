# -*- coding: utf-8 -*-
"""推荐辅助函数单元测试。"""

from __future__ import annotations

from shike.services.recommend import (
    _apply_one_relax,
    _has_hard_filters,
    apply_favorite_boost,
    generate_reason,
    merge_user_preferences,
)


def test_generate_reason_by_keyword():
    assert "辛苦" in generate_reason("加班好累")
    assert "仪式感" in generate_reason("今天想庆祝一下")
    assert generate_reason("随便吃点", "兜底理由") == "兜底理由"


def test_has_hard_filters():
    assert _has_hard_filters(None) is False
    assert _has_hard_filters({}) is False
    assert _has_hard_filters({"spicy_level_max": 0}) is True
    assert _has_hard_filters({"exclude_allergens": ["花生"]}) is True
    assert _has_hard_filters({"exclude_allergens": []}) is False


def test_apply_one_relax_time_and_cuisine():
    f, desc = _apply_one_relax({"estimated_time_max": 15}, "time")
    assert f["estimated_time_max"] == 30
    assert "15->30" in desc

    f2, desc2 = _apply_one_relax({"cuisine_main": "川菜"}, "cuisine")
    assert "cuisine_main" not in f2
    assert "川菜" in desc2

    f3, desc3 = _apply_one_relax({}, "time")
    assert desc3 == ""


def test_merge_user_preferences_request_wins_and_allergens_merge():
    merged = merge_user_preferences(
        {"spicy_level_max": 1, "exclude_allergens": ["花生"]},
        {
            "spicy_level_max": 0,
            "cuisine_main": "粤菜",
            "exclude_allergens": ["花生", "牛奶"],
        },
    )
    assert merged["spicy_level_max"] == 1
    assert merged["cuisine_main"] == "粤菜"
    assert merged["exclude_allergens"] == ["花生", "牛奶"]


def test_apply_favorite_boost_marks_and_reorders():
    items = [
        {"id": "a", "title": "A"},
        {"id": "b", "title": "B"},
        {"id": "c", "title": "C"},
    ]
    out = apply_favorite_boost(items, ["c", "a"])
    assert [x["id"] for x in out] == ["a", "c", "b"]
    assert out[0]["is_favorited"] is True
    assert out[2]["is_favorited"] is False
