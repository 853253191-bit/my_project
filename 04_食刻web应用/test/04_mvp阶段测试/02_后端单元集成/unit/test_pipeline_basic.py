# -*- coding: utf-8 -*-
"""Pipeline / 检索基础单元测试（原 e2e_api/test_basic.py）。"""

from __future__ import annotations

import sys
from pathlib import Path

# backend 根（含 pipeline）+ backend/src（含 shike）
_PROJECT = Path(__file__).resolve().parents[4]  # 04_食刻web应用
_BACKEND = _PROJECT / "backend"
for p in (_BACKEND, _BACKEND / "src"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from pipeline.clean import clean_recipes, validate_recipe
from pipeline.seed_recipes import generate_seed_recipes
from shike.db.repository import RecipeRepository
from shike.rag.chunk import chunk_recipe
from shike.rag.retriever import build_query


def test_generate_seed_recipes_count():
    recipes = generate_seed_recipes(100)
    assert len(recipes) == 100


def test_clean_recipes():
    recipes = generate_seed_recipes(50)
    cleaned = clean_recipes(recipes)
    assert len(cleaned) == 50
    assert all(validate_recipe(r) for r in cleaned)


def test_chunk_recipe():
    recipes = generate_seed_recipes(1)
    chunks = chunk_recipe(recipes[0])
    assert len(chunks) >= 2
    assert chunks[0].metadata["type"] == "overview"


def test_sqlite_upsert(tmp_path):
    db_path = tmp_path / "test.db"
    repo = RecipeRepository(db_path)
    recipes = generate_seed_recipes(5)
    repo.upsert_many(clean_recipes(recipes))
    assert repo.count() == 5


def test_build_query():
    q = build_query(
        {"mood": "疲惫", "taste": ["清淡"], "servings": 2, "ingredients": ["鸡蛋"]}
    )
    assert "疲惫" in q
    assert "鸡蛋" in q
