# -*- coding: utf-8 -*-
"""食谱数据清洗与标准化。"""

from __future__ import annotations

import hashlib
import re
from typing import Any


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title.strip())


def _ingredients_hash(ingredients: list[dict[str, Any]]) -> str:
    names = sorted(i.get("name", "") for i in ingredients)
    return hashlib.md5("|".join(names).encode()).hexdigest()


def deduplicate(recipes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for r in recipes:
        key = f"{_normalize_title(r.get('title', ''))}:{_ingredients_hash(r.get('ingredients', []))}"
        if key in seen:
            continue
        seen.add(key)
        result.append(r)
    return result


def validate_recipe(recipe: dict[str, Any]) -> bool:
    if not recipe.get("title", "").strip():
        return False
    ingredients = recipe.get("ingredients", [])
    steps = recipe.get("steps", [])
    if len(ingredients) < 2 or len(steps) < 2:
        return False
    return True


def normalize_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    """字段标准化。"""
    r = dict(recipe)
    r["title"] = r.get("title", "").strip()
    r["description"] = r.get("description", "").strip()
    r["cuisine"] = r.get("cuisine", "家常菜")
    r["difficulty"] = r.get("difficulty", "简单")
    r["cook_minutes"] = r.get("cook_minutes") or 30
    r["servings"] = r.get("servings") or 2

    for tag_field in ("mood_tags", "taste_tags", "health_tags", "weather_tags"):
        tags = r.get(tag_field, [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        r[tag_field] = tags

    ingredients = []
    for i, ing in enumerate(r.get("ingredients", [])):
        if isinstance(ing, str):
            ingredients.append({"name": ing, "amount": "", "unit": ""})
        else:
            ingredients.append({
                "name": ing.get("name", ""),
                "amount": str(ing.get("amount", "")),
                "unit": ing.get("unit", ""),
            })
    r["ingredients"] = ingredients

    steps = []
    for i, step in enumerate(r.get("steps", [])):
        if isinstance(step, str):
            steps.append({"order": i + 1, "text": step})
        else:
            steps.append({"order": step.get("order", i + 1), "text": step.get("text", "")})
    r["steps"] = steps

    return r


def clean_recipes(recipes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_recipe(r) for r in recipes]
    deduped = deduplicate(normalized)
    return [r for r in deduped if validate_recipe(r)]
