# -*- coding: utf-8 -*-
"""PipelineRunner 测试（SPEC §3.2 / §3.3）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manus.pipeline.runner import (
    DuplicateResolveError,
    PipelineRunner,
    StepNotAwaitingError,
)
from manus.pipeline.state import PipelineState, create_initial_state


@pytest.fixture
def runner(tmp_runs_dir, minimal_config_dict):
    run_manager = MagicMock()
    run_manager.runs_dir = tmp_runs_dir
    run_manager.load_state = MagicMock(
        return_value=create_initial_state(run_id="run-1", run_date="2026-07-07")
    )
    run_manager.save_state = MagicMock()
    return PipelineRunner(config=minimal_config_dict, run_manager=run_manager)


class TestRunSingleStep:
    @pytest.mark.asyncio
    async def test_step0_sets_awaiting_approval(self, runner: PipelineRunner):
        with patch.object(runner, "_execute_agent", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"news_items": [], "step_output_summary": "Top5"}
            state = await runner.run_single_step("run-1", step=0)
        assert state.status == "awaiting_step_approval"
        assert state.pending_approval_step == 0

    @pytest.mark.asyncio
    async def test_invalid_step_raises(self, runner: PipelineRunner):
        with pytest.raises(ValueError):
            await runner.run_single_step("run-1", step=6)


class TestResolveStep:
    @pytest.mark.asyncio
    async def test_proceed_requires_awaiting(self, runner: PipelineRunner):
        state = create_initial_state(run_id="run-1", run_date="2026-07-07")
        state.status = "running"
        runner.run_manager.load_state.return_value = state
        with pytest.raises(StepNotAwaitingError):
            await runner.resolve_step("run-1", step=0, action="proceed", news_id="n1")

    @pytest.mark.asyncio
    async def test_proceed_step0_requires_news_id(self, runner: PipelineRunner):
        state = create_initial_state(run_id="run-1", run_date="2026-07-07")
        state.status = "awaiting_step_approval"
        state.pending_approval_step = 0
        runner.run_manager.load_state.return_value = state
        with pytest.raises(ValueError, match="news_id"):
            await runner.resolve_step("run-1", step=0, action="proceed")

    @pytest.mark.asyncio
    async def test_proceed_step0_writes_selection(self, runner: PipelineRunner):
        state = create_initial_state(run_id="run-1", run_date="2026-07-07")
        state.status = "awaiting_step_approval"
        state.pending_approval_step = 0
        state.news_items = [{"id": "n1", "title": "t"}]  # type: ignore[list-item]
        runner.run_manager.load_state.return_value = state
        with patch.object(runner, "run_single_step", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = state
            await runner.resolve_step("run-1", step=0, action="proceed", news_id="n1")
        assert state.selected_news_id == "n1"
        assert state.phase == "research"

    @pytest.mark.asyncio
    async def test_rerun_clears_fields(self, runner: PipelineRunner, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.status = "awaiting_step_approval"
        state.pending_approval_step = 1
        runner.run_manager.load_state.return_value = state
        with patch.object(runner, "run_single_step", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = state
            await runner.resolve_step("run-1", step=1, action="rerun")
        assert state.component_node is None

    @pytest.mark.asyncio
    async def test_change_direction_step1(self, runner: PipelineRunner, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.status = "awaiting_step_approval"
        state.pending_approval_step = 1
        runner.run_manager.load_state.return_value = state
        with patch.object(runner, "run_single_step", new_callable=AsyncMock):
            await runner.resolve_step("run-1", step=1, action="change_direction")
        assert state.phase == "collect"
        assert state.pending_approval_step == 0

    @pytest.mark.asyncio
    async def test_duplicate_proceed_raises_409_equivalent(self, runner: PipelineRunner):
        state = create_initial_state(run_id="run-1", run_date="2026-07-07")
        state.status = "running"
        state.pending_approval_step = 1
        runner.run_manager.load_state.return_value = state
        with pytest.raises(DuplicateResolveError):
            await runner.resolve_step("run-1", step=0, action="proceed", news_id="n1")

    @pytest.mark.asyncio
    async def test_block_proceed_on_outlook_stop(self, runner: PipelineRunner, filled_pipeline_state_dict):
        state = PipelineState.model_validate(filled_pipeline_state_dict)
        state.status = "awaiting_step_approval"
        state.pending_approval_step = 1
        state.gate_outlook_result = "stop"
        state.approval_hints = {"block_proceed": True, "outlook_stop": True}
        runner.run_manager.load_state.return_value = state
        with pytest.raises(ValueError, match="block_proceed"):
            await runner.resolve_step("run-1", step=1, action="proceed")


class TestAutoRunMode:
    @pytest.mark.asyncio
    async def test_auto_mode_skips_approval_pause(self, tmp_runs_dir, minimal_config_dict):
        minimal_config_dict["workflow"]["step_approval_required"] = False
        run_manager = MagicMock()
        run_manager.load_state.return_value = create_initial_state(run_id="run-1", run_date="2026-07-07")
        runner = PipelineRunner(config=minimal_config_dict, run_manager=run_manager)
        with patch.object(runner, "_execute_agent", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"step_output_summary": "ok"}
            state = await runner.run_single_step("run-1", step=1)
        # 全自动模式不在每步暂停，status 不应为 awaiting（实现可设为 running 或 completed 链式）
        assert state.pending_approval_step != 1 or state.status != "awaiting_step_approval"
