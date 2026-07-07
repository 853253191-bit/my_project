# -*- coding: utf-8 -*-
"""BOM 加深拆解 prompt 与判定（SPEC §4.3）。"""

from __future__ import annotations

from typing import Any


def is_deepen_mode(state: dict[str, Any]) -> bool:
    return bool(state.get("deepen_bom")) or int(state.get("bom_deepen_count") or 0) > 0


def target_decomposition_depth(state: dict[str, Any]) -> int:
    node = state.get("component_node") or {}
    prev = node.get("decomposition_depth", 2) if isinstance(node, dict) else 2
    return min(int(prev) + 1, 6)


def deepen_bom_instruction(state: dict[str, Any]) -> str:
    count = int(state.get("bom_deepen_count") or 1)
    target = target_decomposition_depth(state)
    return (
        f"【加深拆解 第{count}次】在现有 BOM 基础上比共识多拆一层："
        f"decomposition_depth 至少 {target}；"
        f"为每个 components 补充更细 upstream_hints；"
        f"horizontal_branches 补充材料/工艺/设备子环节。"
    )


def build_agent2_user_prompt(state: dict[str, Any], selected: dict[str, Any]) -> str:
    parts = [
        "基于新闻拆解 AI 硬件产业链 BOM，输出 JSON，字段 component_node（含 terminal_demand.outlook_2_3y）。",
        f"新闻: {selected.get('title', '')} {selected.get('summary', '')}",
        "基础要求：decomposition_depth 3～4；components 至少 4 项且含 upstream_hints；horizontal_branches 至少 2 条。",
    ]
    if is_deepen_mode(state):
        parts.append(deepen_bom_instruction(state))
        if state.get("component_node"):
            parts.append(f"当前 BOM（需在此基础上向下加深）：{state['component_node']}")
    return "\n".join(parts)


def build_agent3_system_prompt(state: dict[str, Any]) -> str:
    deepen = is_deepen_mode(state)
    lines = [
        "你是产业链瓶颈研究员。",
        "对 component_node 中各环节评估四特征：mandatory、oligopoly、slow_expansion、low_coverage（true/false/unknown）。",
        "优先选择四特征 true 越多越好（至少 3 个 true）的环节作为瓶颈。",
        "每条 bottleneck 需含 mismatch_hypothesis、evidence[]、layer（module/device/material/process/equipment）。",
    ]
    if deepen:
        lines.append(
            "当前为加深 BOM 模式：基于更细粒度拆解，至少输出 3 条 bottlenecks，每条至少 3 个四特征为 true。"
        )
    else:
        lines.append("至少输出 3 条 bottlenecks，其中至少 2 条满足 ≥3 个四特征为 true。")
    return " ".join(lines)


def build_agent3_user_prompt(state: dict[str, Any], rag_text: str) -> str:
    deepen = is_deepen_mode(state)
    parts = [
        rag_text,
        "识别产业链瓶颈，输出 JSON：bottlenecks[]、ripple_notes。",
        f"component_node={state.get('component_node')}",
    ]
    if deepen:
        parts.append("请沿加深后的 BOM 逐层下钻，覆盖材料/工艺/设备子环节，不要重复上一轮已识别的粗粒度瓶颈。")
    return "\n\n".join(p for p in parts if p)
