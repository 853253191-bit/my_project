# -*- coding: utf-8 -*-
"""Agent3：瓶颈识别。"""

from __future__ import annotations

from typing import Any

from manus.llm import invoke_llm_json
from manus.pipeline.bom_deepen import build_agent3_system_prompt, build_agent3_user_prompt, is_deepen_mode
from manus.pipeline.bom_fallback import bom_to_fallback_bottlenecks, format_bom_chain_text
from manus.pipeline.gates import build_approval_hints
from manus.pipeline.progress import emit_progress
from manus.pipeline.state import PipelineState
from manus.schemas.models import BottleneckItem

from manus.rag.context import bottleneck_hint_from_state, fetch_agent_rag_context


async def run_agent3(state: dict[str, Any], config: dict[str, Any] | Any) -> dict[str, Any]:
    hint = bottleneck_hint_from_state(state)
    emit_progress("检索策略库与案例库…")
    rag_text, rag_errors = fetch_agent_rag_context(
        "agent3", config, query_extra=hint, bottleneck_name=hint, include_cases=True
    )
    if is_deepen_mode(state):
        emit_progress("基于加深后的 BOM 识别瓶颈…")
    else:
        emit_progress("调用大模型识别产业链瓶颈…")

    ripple = ""
    try:
        data = await invoke_llm_json(
            config,
            [
                {"role": "system", "content": build_agent3_system_prompt(state)},
                {"role": "user", "content": build_agent3_user_prompt(state, rag_text)},
            ],
        )
        bottlenecks = [BottleneckItem.model_validate(b) for b in data.get("bottlenecks", [])]
        ripple = data.get("ripple_notes", "") or ""
    except Exception:
        bottlenecks = []

    bom_fallback_used = False
    component_node = state.get("component_node")
    if not bottlenecks and component_node:
        bom_fallback_used = True
        news_id = state.get("selected_news_id") or ""
        emit_progress("瓶颈识别无结果，直接输出 Agent2 产业链拆解…")
        bottlenecks = [
            BottleneckItem.model_validate(b)
            for b in bom_to_fallback_bottlenecks(component_node, news_id=news_id)
        ]
        ripple = format_bom_chain_text(component_node)

    suggest = len(bottlenecks) < 2 and not bom_fallback_used
    ps = PipelineState.model_validate(
        {
            "run_id": state.get("run_id", "x"),
            "run_date": state.get("run_date", "2026-01-01"),
            "bottlenecks": [b.model_dump(mode="json") for b in bottlenecks],
            "errors": state.get("errors", []),
        }
    )
    hints = build_approval_hints(ps, step=2, suggest_deepen_bom=suggest)
    if bom_fallback_used:
        summary = f"瓶颈识别无结果，已输出产业链 {len(bottlenecks)} 个环节供下游匹配"
    elif is_deepen_mode(state):
        summary = f"加深拆解后识别瓶颈 {len(bottlenecks)} 个"
    else:
        summary = f"识别瓶颈 {len(bottlenecks)} 个"

    return {
        "bottlenecks": [b.model_dump(mode="json") for b in bottlenecks],
        "ripple_notes": ripple,
        "approval_hints": hints.model_dump(mode="json"),
        "suggest_deepen_bom": suggest,
        "bom_fallback_used": bom_fallback_used,
        "step_output_summary": summary,
        "rag_contexts": {**(state.get("rag_contexts") or {}), "agent3": rag_text},
        "errors": list(state.get("errors") or []) + rag_errors,
    }
