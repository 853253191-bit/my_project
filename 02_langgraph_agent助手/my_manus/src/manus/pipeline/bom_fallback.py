# -*- coding: utf-8 -*-
"""瓶颈识别无结果时，回退为 Agent2 产业链拆解输出。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def _node_dict(component_node: Any) -> dict[str, Any]:
    if component_node is None:
        return {}
    if isinstance(component_node, dict):
        return component_node
    if hasattr(component_node, "model_dump"):
        return component_node.model_dump(mode="json")
    return {}


def format_bom_chain_text(component_node: Any) -> str:
    """将 component_node 格式化为可读产业链文本（供 step 输出与 ripple_notes）。"""
    node = _node_dict(component_node)
    if not node:
        return "（无产业链拆解数据）"

    lines = ["【产业链拆解结果（瓶颈识别无结果，直接沿用 BOM）】"]
    td = node.get("terminal_demand") or {}
    lines.append(f"终端需求：{td.get('description', '')}")
    lines.append(f"2～3 年 outlook：{td.get('outlook_2_3y', '')}；依据：{td.get('backing', '')}")
    lines.append(f"拆解深度：{node.get('decomposition_depth', '-')}")
    lines.append("核心环节：")
    for comp in node.get("components") or []:
        name = comp.get("name", "")
        lines.append(
            f"- {name}（{comp.get('category', '')}，价值量 {comp.get('value_share', '')}）"
            f"：{comp.get('growth_driver', '')}；上游 {comp.get('upstream_hints', [])}"
        )
    branches = node.get("horizontal_branches") or []
    if branches:
        lines.append("横向/上游分支：")
        for br in branches:
            lines.append(f"- [{br.get('type', '')}] {br.get('node', '')}：{br.get('rationale', '')}")
    return "\n".join(lines)


def bom_to_fallback_bottlenecks(component_node: Any, news_id: str = "") -> list[dict[str, Any]]:
    """将 BOM 各环节转为可下游消费的 pseudo-bottleneck 列表。"""
    node = _node_dict(component_node)
    items: list[dict[str, Any]] = []
    for comp in node.get("components") or []:
        name = comp.get("name") or "未知环节"
        items.append(
            {
                "id": f"bom-{uuid4().hex[:8]}",
                "component": name,
                "bottleneck_name": name,
                "layer": "module",
                "traits": {
                    "mandatory": "unknown",
                    "oligopoly": "unknown",
                    "slow_expansion": "unknown",
                    "low_coverage": "unknown",
                },
                "mismatch_hypothesis": (
                    f"产业链环节「{name}」来自 BOM 拆解（新闻 {news_id or '-'}），"
                    f"增长驱动：{comp.get('growth_driver', '待验证')}"
                ),
                "evidence": ["Agent2 产业链拆解", "Agent3 瓶颈识别无结果时的 BOM 回退"],
            }
        )
    for br in node.get("horizontal_branches") or []:
        node_name = br.get("node") or "上游分支"
        items.append(
            {
                "id": f"bom-br-{uuid4().hex[:8]}",
                "component": node_name,
                "bottleneck_name": node_name,
                "layer": "material",
                "traits": {
                    "mandatory": "unknown",
                    "oligopoly": "unknown",
                    "slow_expansion": "unknown",
                    "low_coverage": "unknown",
                },
                "mismatch_hypothesis": f"横向分支「{node_name}」：{br.get('rationale', '')}",
                "evidence": ["Agent2 horizontal_branches", "BOM 回退"],
            }
        )
    return items
