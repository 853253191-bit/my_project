# -*- coding: utf-8 -*-
"""意图解析：自然语言 → 结构化筛选字段。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from shike.config import AppConfig
from shike.models.schemas import GenerateRequest

PARSE_INTENT_SYSTEM = """你是食刻 App 的意图解析助手。根据用户一句话，提取做菜偏好，输出严格 JSON：
{
  "query_text": "改写后的检索短句",
  "filters": {
    "greasiness_max": null或1-5整数,
    "spicy_level_max": null或0-5整数,
    "cuisine_main": null或菜系名（川菜/粤菜/鲁菜等，禁止家常菜）,
    "ai_difficulty": null或easy/medium/hard,
    "estimated_time_max": null或分钟整数,
    "exclude_allergens": [],
    "include_diet_labels": []
  },
  "form": {
    "mood": "",
    "taste": [],
    "spice_level": 0,
    "servings": 2,
    "cook_time": "30分钟内",
    "health_goal": "无",
    "ingredients": [],
    "free_text": ""
  }
}
规则：无法判断的字段用 null 或默认值；只输出 JSON。"""


def form_to_dict(req: GenerateRequest) -> dict[str, Any]:
    return req.model_dump()


def merge_chat_intent(form: dict[str, Any] | None, message: str) -> dict[str, Any]:
    """将对话修改意图合并到检索上下文。"""
    base = dict(form) if form else {}
    base["free_text"] = f"{base.get('free_text', '')} {message}".strip()
    return base


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("意图解析结果不是对象")
    return obj


def parse_user_intent(config: AppConfig, text: str) -> dict[str, Any]:
    """调用 LLM 解析用户输入，返回 recommend / 表单回填结构。"""
    api_key = (
        os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("DASHSCOPE_API_KEY", "").strip()
        or config.llm.api_key
    )
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or config.llm.base_url
    model = os.getenv("OPENAI_MODEL", "").strip() or config.llm.model
    if not api_key:
        raise RuntimeError("未配置 LLM API Key")

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PARSE_INTENT_SYSTEM},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    data = _extract_json(content)

    filters = data.get("filters") or {}
    # 清理 null
    clean_filters = {k: v for k, v in filters.items() if v is not None and v != []}
    form = data.get("form") or {}
    form.setdefault("free_text", text)
    return {
        "query_text": data.get("query_text") or text,
        "filters": clean_filters,
        "form": form,
    }
