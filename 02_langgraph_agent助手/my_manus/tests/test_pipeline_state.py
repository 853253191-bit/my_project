# -*- coding: utf-8 -*-
"""PipelineState 测试（SPEC §3.1）。"""

from __future__ import annotations

from manus.pipeline.state import PipelineState, create_initial_state


class TestCreateInitialState:
    def test_defaults(self):
        state = create_initial_state(run_id="run-abc", run_date="2026-07-07")
        assert state.run_id == "run-abc"
        assert state.run_date == "2026-07-07"
        assert state.phase == "collect"
        assert state.status == "pending"
        assert state.pending_approval_step is None
        assert state.news_items == []
        assert state.errors == []

    def test_round_trip_json(self, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        restored = PipelineState.model_validate(state.model_dump(mode="json"))
        assert restored.run_id == state.run_id
        assert restored.pending_approval_step == state.pending_approval_step
        assert len(restored.bottlenecks) == len(state.bottlenecks)
