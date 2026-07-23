# -*- coding: utf-8 -*-
"""Prompt 模板。"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """你是「食刻」智能饮食顾问。你必须基于提供的食谱知识库内容回答，不得编造不存在的菜品或步骤。

输出要求：
1. 用中文回答
2. 结合用户的心情、口味、人数、天气等情境个性化推荐
3. 若知识库中没有合适内容，诚实告知并给出通用建议
4. 注意饮食安全：提醒过敏风险、生食注意事项
5. 回答结构清晰：菜名、推荐理由、食材清单（含用量）、烹饪步骤、预估时间、营养提示

请直接输出食谱内容，使用 Markdown 格式。"""

CHAT_SYSTEM_PROMPT = """你是「食刻」智能饮食顾问。用户已对上一份食谱提出修改意见，请基于知识库内容和对话历史，输出调整后的完整食谱。

保持 Markdown 格式，包含：菜名、食材、步骤、时间、注意事项。"""


def build_generate_prompt(
    form: dict[str, Any],
    context_chunks: list[dict[str, Any]],
    weather: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    context_text = "\n\n---\n\n".join(c["text"] for c in context_chunks)
    weather_text = ""
    if weather:
        weather_text = f"\n当前天气：{weather.get('city', '')} {weather.get('weather', '')} {weather.get('temperature', '')}"

    user_msg = f"""用户需求：
- 心情：{form.get('mood', '')}
- 口味：{', '.join(form.get('taste', []))}
- 辣度：{form.get('spice_level', 0)}
- 人数：{form.get('servings', 2)}人
- 耗时要求：{form.get('cook_time', '')}
- 健康目标：{form.get('health_goal', '无')}
- 现有食材：{', '.join(form.get('ingredients', []))}
- 补充说明：{form.get('free_text', '')}{weather_text}

参考食谱知识库：
{context_text}

请基于以上信息，生成一份个性化食谱推荐。"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def build_chat_prompt(
    form: dict[str, Any] | None,
    last_recipe: str,
    message: str,
    context_chunks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    context_text = "\n\n---\n\n".join(c["text"] for c in context_chunks)
    form_text = json.dumps(form, ensure_ascii=False) if form else "无"

    user_msg = f"""原始需求：{form_text}

上一份食谱：
{last_recipe}

用户修改意见：{message}

参考食谱知识库：
{context_text}

请输出调整后的完整食谱。"""

    return [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
