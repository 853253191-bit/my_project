# -*- coding: utf-8 -*-
"""字段清除矩阵测试（SPEC §3.2.5）。"""

from __future__ import annotations

import copy

import pytest

from manus.pipeline.field_clear import apply_field_clear
from manus.pipeline.state import PipelineState


@pytest.fixture
def state(filled_pipeline_state_dict) -> PipelineState:
    return PipelineState.model_validate(copy.deepcopy(filled_pipeline_state_dict))


class TestRerunFieldClear:
    def test_step0_rerun_keeps_downstream(self, state: PipelineState):
        apply_field_clear(state, step=0, action="rerun")
        assert state.component_node is not None
        assert state.bottlenecks

    def test_step1_rerun_clears_phase2(self, state: PipelineState):
        apply_field_clear(state, step=1, action="rerun")
        assert state.component_node is None
        assert state.bottlenecks == []
        assert state.validations == []
        assert state.suppliers == []
        assert state.final_report_md == ""

    def test_step2_rerun_clears_bottlenecks_downstream(self, state: PipelineState):
        apply_field_clear(state, step=2, action="rerun")
        assert state.component_node is not None
        assert state.bottlenecks == []
        assert state.validations == []

    def test_step3_rerun_clears_quant_downstream(self, state: PipelineState):
        apply_field_clear(state, step=3, action="rerun")
        assert state.bottlenecks
        assert state.validations == []
        assert state.red_team is None
        assert state.checklist_gate is None

    def test_step4_rerun_clears_suppliers(self, state: PipelineState):
        state.suppliers = []  # 将由实现填充；此处测清除逻辑
        apply_field_clear(state, step=4, action="rerun")
        assert state.suppliers == []
        assert state.final_report_md == ""

    def test_step5_rerun_clears_report_only(self, state: PipelineState):
        state.final_report_md = "# 报告"
        state.report_output_path = "output/reports/x.md"
        apply_field_clear(state, step=5, action="rerun")
        assert state.final_report_md == ""
        assert state.report_output_path is None


class TestChangeDirectionFieldClear:
    def test_step1_change_direction_back_to_collect(self, state: PipelineState):
        apply_field_clear(state, step=1, action="change_direction")
        assert state.phase == "collect"
        assert state.pending_approval_step == 0
        assert state.selected_news_id is None
        assert state.component_node is None

    def test_step3_change_direction_keeps_agent1_3(self, state: PipelineState):
        apply_field_clear(state, step=3, action="change_direction")
        assert state.component_node is not None
        assert state.bottlenecks == []
        assert state.pending_approval_step == 2

    def test_errors_preserved_on_rerun(self, state: PipelineState):
        state.errors.append("prev_error")
        apply_field_clear(state, step=1, action="rerun")
        assert "prev_error" in state.errors
