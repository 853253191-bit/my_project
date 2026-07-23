# -*- coding: utf-8 -*-
"""推荐结果菜名去重：本地模糊 + LLM 语义判重。"""

from __future__ import annotations

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any

from openai import OpenAI

from shike.config import AppConfig

logger = logging.getLogger(__name__)

# 标题同义词归一（含常见写法差异）
TITLE_SYNONYMS: dict[str, str] = {
    "西红柿": "番茄",
    "马铃薯": "土豆",
    "地瓜": "红薯",
    "番薯": "红薯",
    "包菜": "卷心菜",
    "圆白菜": "卷心菜",
    "花椰菜": "花菜",
    "菜花": "花菜",
    "青瓜": "黄瓜",
    "新奥尔良": "奥尔良",
    "鸡翅中": "鸡翅",
    "鸡翅根": "鸡翅",
    "烤鸡翅": "烤翅",
    "炸鸡翅": "炸翅",
}

PAREN_RE = re.compile(r"[（(【\[].*?[）)】\]]")
PREFIXES = (
    "家常",
    "经典",
    "正宗",
    "简易",
    "简单",
    "秘制",
    "懒人",
    "新手",
    "零失败",
    "超简单",
    "妈妈",
    "空气炸锅",
    "烤箱",
)

# 本地模糊：达到此阈值视为重复
FUZZY_DUP_THRESHOLD = 0.86

LLM_SYSTEM = """你是菜谱去重助手。给定若干候选菜名（按推荐相关度排序），请去掉「实质同一道菜、仅写法不同」的重复项，保留最具代表性的一条。

应判为重复的例子：
- 新奥尔良烤翅 vs 奥尔良烤鸡翅
- 番茄炒蛋 vs 西红柿炒鸡蛋
- 红烧肉（家常版） vs 经典红烧肉

不应判为重复：
- 红烧牛肉 vs 清炖牛肉
- 番茄炒蛋 vs 番茄蛋汤
- 宫保鸡丁 vs 鱼香肉丝

只输出 JSON：
{"keep_indices": [0, 2, 5], "reason": "简短说明"}
keep_indices 为保留项在原列表中的下标（从 0 开始），保持原有先后顺序，不要新增索引。"""


def normalize_title(title: str) -> str:
    t = re.sub(r"\s+", "", (title or "").strip())
    t = re.sub(r"[‼️✅~～\-—_]+", "", t)
    return t


def normalize_title_core(title: str) -> str:
    t = normalize_title(title)
    t = PAREN_RE.sub("", t)
    for p in PREFIXES:
        if t.startswith(p):
            t = t[len(p) :]
    for src, dst in TITLE_SYNONYMS.items():
        t = t.replace(src, dst)
    for suffix in ("的做法", "教程", "步骤", "图解"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
    return t


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ca, cb = normalize_title_core(a), normalize_title_core(b)
    if ca and cb and ca == cb:
        return 1.0
    sim_full = SequenceMatcher(None, na, nb).ratio()
    sim_core = SequenceMatcher(None, ca, cb).ratio() if ca and cb else 0.0
    return max(sim_full, sim_core)


def dedupe_by_fuzzy(
    items: list[dict[str, Any]],
    keep: int,
    threshold: float = FUZZY_DUP_THRESHOLD,
) -> list[dict[str, Any]]:
    """按标题模糊相似度贪心去重，保留先出现（更相关）的。"""
    kept: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title") or "")
        if not title:
            continue
        dup = False
        for prev in kept:
            if title_similarity(title, str(prev.get("title") or "")) >= threshold:
                dup = True
                break
        if not dup:
            kept.append(item)
        if len(kept) >= keep:
            break
    return kept


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
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
        raise ValueError("LLM 去重结果不是对象")
    return obj


def dedupe_by_llm(
    config: AppConfig,
    items: list[dict[str, Any]],
    keep: int,
) -> list[dict[str, Any]]:
    """一次 LLM 调用，从候选中保留语义不重复的前 keep 条。"""
    if len(items) <= 1:
        return items[:keep]

    api_key = (
        os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("DASHSCOPE_API_KEY", "").strip()
        or config.llm.api_key
    )
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or config.llm.base_url
    model = os.getenv("OPENAI_MODEL", "").strip() or config.llm.model
    if not api_key:
        raise RuntimeError("未配置 LLM API Key，无法做菜名语义去重")

    lines = [f"{i}. {it.get('title') or ''}" for i, it in enumerate(items)]
    user_prompt = (
        f"请从下列 {len(items)} 个菜名中去重，最多保留 {keep} 个：\n"
        + "\n".join(lines)
    )

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": LLM_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    data = _extract_json(content)
    indices = data.get("keep_indices") or []
    if not isinstance(indices, list):
        raise ValueError("keep_indices 格式错误")

    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for raw in indices:
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(items) or idx in seen:
            continue
        seen.add(idx)
        out.append(items[idx])
        if len(out) >= keep:
            break

    # LLM 若漏返回，按原序补足到 keep（且与已选做模糊去重）
    if len(out) < keep:
        for item in items:
            if item in out:
                continue
            title = str(item.get("title") or "")
            if any(
                title_similarity(title, str(p.get("title") or "")) >= FUZZY_DUP_THRESHOLD
                for p in out
            ):
                continue
            out.append(item)
            if len(out) >= keep:
                break

    logger.info(
        "LLM 菜名去重: 候选=%s 保留=%s reason=%s",
        len(items),
        len(out),
        data.get("reason", ""),
    )
    return out[:keep]


def dedupe_recipe_items(
    config: AppConfig,
    items: list[dict[str, Any]],
    keep: int,
    *,
    use_llm: bool = True,
) -> list[dict[str, Any]]:
    """先模糊去重压缩候选，再 LLM 语义去重到 keep 条。"""
    if keep <= 0 or not items:
        return []
    if len(items) <= keep:
        # 即使数量不多，仍做一轮模糊，避免列表内已有近似重复
        fuzzy = dedupe_by_fuzzy(items, keep=len(items))
        if len(fuzzy) <= keep and not use_llm:
            return fuzzy[:keep]
        if not use_llm:
            return fuzzy[:keep]
        try:
            return dedupe_by_llm(config, fuzzy, keep=keep)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 菜名去重失败，使用模糊结果: %s", exc)
            return fuzzy[:keep]

    # 先用较松阈值压掉明显重复，再交给 LLM
    pre = dedupe_by_fuzzy(items, keep=max(keep * 3, keep), threshold=0.92)
    if not use_llm:
        return dedupe_by_fuzzy(pre, keep=keep)

    try:
        return dedupe_by_llm(config, pre, keep=keep)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM 菜名去重失败，使用模糊结果: %s", exc)
        return dedupe_by_fuzzy(pre, keep=keep)
