# -*- coding: utf-8 -*-
"""OpenAI-compatible LLM 封装（Qwen / DashScope）。"""

from __future__ import annotations

import json
from typing import Any, Callable, TypeVar

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from pydantic import BaseModel

from manus.config import AppConfig, config_to_dict
from manus.pipeline.progress import emit_progress, has_progress_context

T = TypeVar("T", bound=BaseModel)

ProgressCallback = Callable[[str, str], None]


def build_chat_llm(config: AppConfig | dict[str, Any]) -> ChatOpenAI:
    cfg = config_to_dict(config)
    llm_cfg = cfg["llm"]
    return ChatOpenAI(
        model=llm_cfg["model"],
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg["base_url"],
        temperature=llm_cfg.get("temperature", 0.2),
        max_tokens=llm_cfg.get("max_tokens", 8192),
    )


def _build_async_client(config: AppConfig | dict[str, Any]) -> tuple[AsyncOpenAI, str]:
    cfg = config_to_dict(config)
    llm_cfg = cfg["llm"]
    return (
        AsyncOpenAI(api_key=llm_cfg["api_key"], base_url=llm_cfg["base_url"]),
        llm_cfg["model"],
    )


async def invoke_llm_json_stream(
    config: AppConfig | dict[str, Any],
    messages: list[dict[str, str]],
    on_chunk: ProgressCallback | None = None,
) -> dict[str, Any]:
    """流式调用 LLM，将思考/输出片段通过 on_chunk(kind, text) 推送。"""
    client, model = _build_async_client(config)
    emit_progress("大模型开始生成（流式）…", kind="llm_start")
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        response_format={"type": "json_object"},
        temperature=config_to_dict(config)["llm"].get("temperature", 0.2),
    )
    parts: list[str] = []
    thinking_parts: list[str] = []
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            thinking_parts.append(reasoning)
            if on_chunk:
                on_chunk("thinking", reasoning)
            else:
                emit_progress(reasoning, kind="thinking")
        content = delta.content
        if content:
            parts.append(content)
            if on_chunk:
                on_chunk("llm_output", content)
            else:
                emit_progress(content, kind="llm_output")
    text = "".join(parts)
    if thinking_parts:
        emit_progress(f"思考完成，共 {len(''.join(thinking_parts))} 字", kind="thinking_done")
    emit_progress("大模型生成完成，解析 JSON…", kind="llm_done")
    return json.loads(text) if text else {}


async def invoke_llm_structured(
    config: AppConfig | dict[str, Any],
    messages: list[dict[str, str]],
    schema: type[T],
) -> T:
    """调用 LLM 并解析为 Pydantic 模型。"""
    llm = build_chat_llm(config)
    structured = llm.with_structured_output(schema)
    result = await structured.ainvoke(messages)
    if isinstance(result, schema):
        return result
    return schema.model_validate(result)


async def invoke_llm_json(
    config: AppConfig | dict[str, Any],
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """有进度上下文时走流式，便于页面展示思考过程。"""
    if has_progress_context():
        return await invoke_llm_json_stream(config, messages)
    llm = build_chat_llm(config)
    llm_json = llm.bind(response_format={"type": "json_object"})
    resp = await llm_json.ainvoke(messages)
    content = resp.content
    if isinstance(content, str):
        return json.loads(content)
    return dict(content)
