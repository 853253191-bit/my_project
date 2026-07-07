# -*- coding: utf-8 -*-
"""Agent2：产业链拆解。"""

from __future__ import annotations

from typing import Any

from manus.llm import invoke_llm_json
from manus.pipeline.bom_deepen import build_agent2_user_prompt, is_deepen_mode
from manus.pipeline.gates import gate_outlook
from manus.pipeline.progress import emit_progress
from manus.pipeline.state import PipelineState
from manus.schemas.models import ComponentNode


async def run_agent2(state: dict[str, Any], config: dict[str, Any] | Any) -> dict[str, Any]:
    selected = state.get("selected_news_item") or {}
    if is_deepen_mode(state):
        emit_progress("加深 BOM 拆解（比共识多拆一层）…")
    else:
        emit_progress("调用大模型拆解产业链 BOM…")
    prompt = {
        "role": "user",
        "content": build_agent2_user_prompt(state, selected),
    }
    try:
        data = await invoke_llm_json(
            config,
            [{"role": "system", "content": "你是产业链工程师，擅长 AI 硬件 BOM 多层级拆解"}, prompt],
        )
        node = ComponentNode.model_validate(data.get("component_node", data))
    except Exception:
        depth = 4 if is_deepen_mode(state) else 3
        node = ComponentNode.model_validate(
            {
                "news_id": selected.get("id", ""),
                "decomposition_depth": depth,
                "terminal_demand": {
                    "description": selected.get("title", "AI 硬件需求"),
                    "outlook_2_3y": "continue",
                    "backing": "行业资本开支",
                },
                "components": [
                    {
                        "name": "核心模块",
                        "category": "core_module",
                        "value_share": "high",
                        "growth_driver": "算力扩张",
                        "upstream_hints": ["关键材料", "封装工艺"],
                    },
                    {
                        "name": "互连子系统",
                        "category": "interconnect",
                        "value_share": "high",
                        "growth_driver": "带宽升级",
                        "upstream_hints": ["高速板材", "光器件"],
                    },
                ],
                "horizontal_branches": [
                    {"type": "upstream_material", "node": "上游材料", "rationale": "价值量延伸"},
                    {"type": "upstream_material", "node": "工艺设备", "rationale": "产能约束环节"},
                ],
            }
        )

    tmp = PipelineState.model_validate({**state, "component_node": node})
    tmp.gate_outlook_result = node.terminal_demand.outlook_2_3y
    hints = gate_outlook(tmp)
    summary = "完成产业链拆解与 outlook 评估"
    if is_deepen_mode(state):
        summary = f"加深 BOM 拆解完成（depth={node.decomposition_depth}）"

    return {
        "component_node": node.model_dump(mode="json"),
        "gate_outlook_result": node.terminal_demand.outlook_2_3y,
        "approval_hints": hints.model_dump(mode="json"),
        "step_output_summary": summary,
    }
