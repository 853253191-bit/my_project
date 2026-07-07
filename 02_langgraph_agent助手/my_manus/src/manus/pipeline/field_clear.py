# -*- coding: utf-8 -*-
"""重跑 / 换向字段清除（SPEC §3.2.5）。"""

from __future__ import annotations

from typing import Literal

from manus.pipeline.state import PipelineState


def _clear_phase2_downstream(state: PipelineState) -> None:
    state.component_node = None
    state.gate_outlook_result = None
    state.bottlenecks = []
    state.ripple_notes = ""
    state.validations = []
    state.red_team = None
    state.checklist_gate = None
    state.confidence = "medium"
    state.suppliers = []
    state.suppliers_excluded = []
    state.bom_fallback_used = False
    state.a_share_candidates = []
    state.final_report_md = ""
    state.report_output_path = None
    state.agent6_mode = "generate"


def _clear_from_bottlenecks(state: PipelineState) -> None:
    state.bottlenecks = []
    state.ripple_notes = ""
    state.validations = []
    state.red_team = None
    state.checklist_gate = None
    state.confidence = "medium"
    state.suppliers = []
    state.suppliers_excluded = []
    state.bom_fallback_used = False
    state.a_share_candidates = []
    state.final_report_md = ""
    state.report_output_path = None
    state.agent6_mode = "generate"


def _clear_from_quant(state: PipelineState) -> None:
    state.validations = []
    state.red_team = None
    state.checklist_gate = None
    state.confidence = "medium"
    state.suppliers = []
    state.suppliers_excluded = []
    state.a_share_candidates = []
    state.final_report_md = ""
    state.report_output_path = None
    state.agent6_mode = "generate"


def _clear_from_suppliers(state: PipelineState) -> None:
    state.suppliers = []
    state.suppliers_excluded = []
    state.final_report_md = ""
    state.report_output_path = None
    state.agent6_mode = "generate"


def apply_field_clear(
    state: PipelineState,
    step: int,
    action: Literal["rerun", "change_direction"],
) -> None:
    """按 step 与 action 清除下游字段，errors 保留追加。"""
    if action == "rerun":
        if step == 0:
            return
        if step == 1:
            _clear_phase2_downstream(state)
        elif step == 2:
            _clear_from_bottlenecks(state)
        elif step == 3:
            _clear_from_quant(state)
        elif step == 4:
            _clear_from_suppliers(state)
        elif step == 5:
            state.final_report_md = ""
            state.report_output_path = None
            state.agent6_mode = "generate"
        return

    if action == "change_direction":
        if step == 1:
            state.selected_news_id = None
            state.selected_news_item = None
            state.phase = "collect"
            state.pending_approval_step = 0
            _clear_phase2_downstream(state)
        elif step == 3:
            _clear_from_bottlenecks(state)
            state.pending_approval_step = 2
