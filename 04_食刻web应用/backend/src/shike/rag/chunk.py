# -*- coding: utf-8 -*-
"""食谱文档切分。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RecipeChunk:
    text: str
    metadata: dict[str, Any]


def _format_ingredients(ingredients: list[dict[str, Any]]) -> str:
    parts = []
    for item in ingredients:
        name = item.get("name", "")
        amount = item.get("amount", "")
        unit = item.get("unit", "")
        parts.append(f"{name} {amount}{unit}".strip())
    return "、".join(parts)


def chunk_recipe(recipe: dict[str, Any]) -> list[RecipeChunk]:
    """将单条食谱切分为概览、步骤、营养三类 chunk。"""
    rid = recipe["id"]
    title = recipe.get("title", "")
    desc = recipe.get("description", "")
    cuisine = recipe.get("cuisine", "")
    mood = "、".join(recipe.get("mood_tags", []))
    taste = "、".join(recipe.get("taste_tags", []))
    health = "、".join(recipe.get("health_tags", []))
    weather = "、".join(recipe.get("weather_tags", []))
    ingredients_text = _format_ingredients(recipe.get("ingredients", []))

    overview = (
        f"菜名：{title}\n"
        f"菜系：{cuisine}\n"
        f"简介：{desc}\n"
        f"心情标签：{mood}\n"
        f"口味标签：{taste}\n"
        f"健康标签：{health}\n"
        f"天气标签：{weather}\n"
        f"烹饪时间：{recipe.get('cook_minutes', '')}分钟\n"
        f"份量：{recipe.get('servings', '')}人份\n"
        f"食材：{ingredients_text}"
    )
    # 若有 AI 平铺标签，追加到概览，增强检索语义
    ai_bits: list[str] = []
    if recipe.get("cuisine_main"):
        ai_bits.append(f"主菜系：{recipe['cuisine_main']}")
    if recipe.get("ai_difficulty"):
        ai_bits.append(f"难度：{recipe['ai_difficulty']}")
    if recipe.get("greasiness") is not None:
        ai_bits.append(f"油腻度：{recipe['greasiness']}")
    if recipe.get("spicy_level") is not None:
        ai_bits.append(f"辣度：{recipe['spicy_level']}")
    if recipe.get("estimated_time") is not None:
        ai_bits.append(f"预估时长：{recipe['estimated_time']}分钟")
    if recipe.get("diet_labels_str"):
        ai_bits.append(f"饮食标签：{recipe['diet_labels_str']}")
    if recipe.get("decision_summary"):
        ai_bits.append(f"推荐语：{recipe['decision_summary']}")
    if ai_bits:
        overview = overview + "\n" + "\n".join(ai_bits)
    chunks: list[RecipeChunk] = [
        RecipeChunk(
            text=overview,
            metadata={"recipe_id": rid, "type": "overview", "title": title},
        )
    ]

    steps = recipe.get("steps", [])
    step_batch = 3
    for i in range(0, len(steps), step_batch):
        batch = steps[i : i + step_batch]
        step_text = "\n".join(f"步骤{s.get('order', j+1)}：{s.get('text', '')}" for j, s in enumerate(batch))
        chunks.append(
            RecipeChunk(
                text=f"菜名：{title}\n{step_text}",
                metadata={
                    "recipe_id": rid,
                    "type": "steps",
                    "title": title,
                    "step_range": f"{i+1}-{i+len(batch)}",
                },
            )
        )

    nutrition = recipe.get("nutrition", {})
    if nutrition:
        nut_text = "、".join(f"{k}:{v}" for k, v in nutrition.items())
        chunks.append(
            RecipeChunk(
                text=f"菜名：{title}\n营养信息：{nut_text}",
                metadata={"recipe_id": rid, "type": "nutrition", "title": title},
            )
        )
    return chunks
