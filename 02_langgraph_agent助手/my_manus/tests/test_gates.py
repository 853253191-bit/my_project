# -*- coding: utf-8 -*-
"""门控逻辑测试（SPEC §3.2.1 / §3.2.2）。"""

from __future__ import annotations

from manus.pipeline.gates import build_approval_hints, gate_checklist, gate_outlook
from manus.pipeline.state import PipelineState
from manus.schemas.models import ChecklistGateResult
from tests.helpers.builders import make_checklist_gate


class TestGateOutlook:
    def test_continue_no_block(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.gate_outlook_result = "continue"
        hints = gate_outlook(state)
        assert hints.block_proceed is False
        assert hints.outlook_stop is False

    def test_stop_blocks_proceed(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.gate_outlook_result = "stop"
        hints = gate_outlook(state)
        assert hints.block_proceed is True
        assert hints.outlook_stop is True

    def test_uncertain_flag(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.gate_outlook_result = "uncertain"
        hints = gate_outlook(state)
        assert hints.outlook_uncertain is True
        assert hints.block_proceed is False


class TestGateChecklist:
    def test_pass_no_hard_fail(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        gate = ChecklistGateResult.model_validate(make_checklist_gate(result="pass"))
        hints = gate_checklist(state, gate)
        assert hints.checklist_hard_fail is False

    def test_hard_fail_hint_without_auto_skip(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        gate = ChecklistGateResult.model_validate(make_checklist_gate(hard_fail=True))
        hints = gate_checklist(state, gate)
        assert hints.checklist_hard_fail is True
        assert hints.block_proceed is False


class TestBuildApprovalHints:
    def test_degraded_flag(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.errors.append("degraded_summary: Agent3 降级")
        hints = build_approval_hints(state, step=2, degraded=True)
        assert hints.degraded is True

    def test_suggest_deepen_bom(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.bottlenecks = state.bottlenecks[:1]
        hints = build_approval_hints(state, step=2, suggest_deepen_bom=True)
        assert hints.suggest_deepen_bom is True
