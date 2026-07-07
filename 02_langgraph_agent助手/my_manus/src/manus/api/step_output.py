# -*- coding: utf-8 -*-
"""各 step 审批视图 output 字段构建。"""

from __future__ import annotations

from typing import Any

from manus.pipeline.state import PipelineState


def as_json(value: Any) -> Any:
    """Pydantic 模型或已是 dict 的值统一转为 JSON 可序列化 dict。"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def as_json_list(items: list[Any] | None) -> list[Any]:
    if not items:
        return []
    return [as_json(item) for item in items]


def build_step_output(state: PipelineState, step: int) -> dict[str, Any]:
    if step == 0:
        return {"news_items": as_json_list(state.news_items)}
    if step == 1:
        return {"component_node": as_json(state.component_node)}
    if step == 2:
        return {
            "bottlenecks": as_json_list(state.bottlenecks),
            "ripple_notes": state.ripple_notes,
        }
    if step == 3:
        return {
            "validations": as_json_list(state.validations),
            "red_team": as_json(state.red_team),
            "checklist_gate": as_json(state.checklist_gate),
        }
    if step == 4:
        return {
            "suppliers": as_json_list(state.suppliers),
            "suppliers_excluded": as_json_list(state.suppliers_excluded),
        }
    return {
        "final_report_md": state.final_report_md,
        "report_output_path": state.report_output_path,
    }
