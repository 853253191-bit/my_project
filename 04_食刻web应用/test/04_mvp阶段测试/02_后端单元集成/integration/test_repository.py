# -*- coding: utf-8 -*-
"""SQLite Repository 集成测试（临时库）。"""

from __future__ import annotations

from pathlib import Path

from shike.db.repository import RecipeRepository


def test_upsert_and_get_by_id(tmp_path: Path):
    repo = RecipeRepository(tmp_path / "recipes.db")
    rid = repo.upsert(
        {
            "id": "r1",
            "title": "番茄炒蛋",
            "description": "快手菜",
            "ingredients": ["鸡蛋", "番茄"],
            "steps": ["炒"],
        }
    )
    assert rid == "r1"
    row = repo.get_by_id("r1")
    assert row is not None
    assert row["title"] == "番茄炒蛋"
    assert repo.count() == 1


def test_site_feedback_save_and_list(tmp_path: Path):
    repo = RecipeRepository(tmp_path / "recipes.db")
    fid = repo.save_site_feedback(
        content="希望能按预算推荐",
        contact="a@b.c",
        category="建议",
        username="guest",
    )
    assert fid > 0
    items, total = repo.list_site_feedback(limit=10)
    assert total == 1
    assert items[0]["content"] == "希望能按预算推荐"
    assert items[0]["category"] == "建议"
