# -*- coding: utf-8 -*-
"""将 SQLite 菜谱格式化为详情 Markdown（不调 LLM）。"""

from __future__ import annotations

from typing import Any

_DIFFICULTY_LABEL = {
    "easy": "简单",
    "medium": "中等",
    "hard": "较难",
}


def ingredient_names(ingredients: Any) -> list[str]:
    """从食材列表提取名称（兼容 str / {name: ...}）。"""
    names: list[str] = []
    if not isinstance(ingredients, list):
        return names
    for item in ingredients:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("ingredient") or "").strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


def _format_ingredient_line(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    name = str(item.get("name") or item.get("ingredient") or "").strip()
    amount = str(item.get("amount") or "").strip()
    unit = str(item.get("unit") or "").strip()
    qty = f"{amount}{unit}".strip()
    if name and qty:
        return f"{name} {qty}"
    return name or qty


def format_recipe_markdown(recipe: dict[str, Any]) -> str:
    """根据库内 ingredients / steps 拼出可读详情。"""
    title = str(recipe.get("title") or "未命名菜谱").strip()
    lines: list[str] = [f"## {title}", ""]

    summary = (
        recipe.get("decision_summary")
        or recipe.get("description")
        or ""
    )
    summary = str(summary).strip()
    if summary:
        lines.append(summary)
        lines.append("")

    meta: list[str] = []
    cuisine = recipe.get("cuisine_main") or recipe.get("cuisine")
    if cuisine:
        meta.append(f"菜系：{cuisine}")
    et = recipe.get("estimated_time") or recipe.get("cook_minutes")
    if et:
        meta.append(f"约 {et} 分钟")
    diff = recipe.get("ai_difficulty") or recipe.get("difficulty")
    if diff:
        meta.append(f"难度：{_DIFFICULTY_LABEL.get(str(diff), diff)}")
    if meta:
        lines.append(" · ".join(meta))
        lines.append("")

    ingredients = recipe.get("ingredients") or []
    if isinstance(ingredients, list) and ingredients:
        lines.append("### 食材")
        lines.append("")
        for raw in ingredients:
            line = _format_ingredient_line(raw)
            if line:
                lines.append(f"- {line}")
        lines.append("")

    steps = recipe.get("steps") or []
    if isinstance(steps, list) and steps:
        lines.append("### 步骤")
        lines.append("")
        for i, step in enumerate(steps, start=1):
            if isinstance(step, str):
                text = step.strip()
                order = i
            elif isinstance(step, dict):
                text = str(step.get("text") or step.get("content") or "").strip()
                order = int(step.get("order") or i)
            else:
                continue
            if text:
                lines.append(f"{order}. {text}")
        lines.append("")

    source = recipe.get("source_url")
    if source:
        lines.append(f"来源：{source}")

    return "\n".join(lines).strip() + "\n"
