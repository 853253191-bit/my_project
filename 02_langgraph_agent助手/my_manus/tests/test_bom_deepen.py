# -*- coding: utf-8 -*-
"""BOM 加深拆解测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from manus.pipeline.bom_deepen import build_agent2_user_prompt, build_agent3_system_prompt, is_deepen_mode
from manus.pipeline.runner import PipelineRunner
from manus.pipeline.state import create_initial_state
from manus.schemas.models import ApprovalHints, NewsItem


def test_is_deepen_mode():
    assert is_deepen_mode({"deepen_bom": True}) is True
    assert is_deepen_mode({"bom_deepen_count": 1}) is True
    assert is_deepen_mode({}) is False


def test_deepen_prompts():
    state = {"bom_deepen_count": 1, "component_node": {"decomposition_depth": 3}}
    assert "加深拆解" in build_agent2_user_prompt(state, {"title": "t", "summary": "s"})
    assert "3 条 bottlenecks" in build_agent3_system_prompt(state)


@pytest.mark.asyncio
async def test_rerun_step2_triggers_deepen_bom(tmp_path, minimal_config_dict):
    from manus.api.run_manager import RunManager

    rm = RunManager(tmp_path)
    state = create_initial_state(run_id="r1", run_date="2026-07-07")
    state.status = "awaiting_step_approval"
    state.pending_approval_step = 2
    state.bom_deepen_count = 0
    state.approval_hints = ApprovalHints(suggest_deepen_bom=True)
    state.news_items = [
        NewsItem(
            id="news-1",
            title="t",
            summary="s",
            source="x",
            url="https://example.com",
            published_at="2026-07-07T00:00:00Z",
            heat_score=0.5,
            relevance_tags=["AI"],
            hardware_focus=True,
            research_hint="h",
        )
    ]
    state.selected_news_item = state.news_items[0]
    state.selected_news_id = "news-1"
    rm.save_state(state)

    runner = PipelineRunner(config=minimal_config_dict, run_manager=rm)
    runner._run_agent_internal = AsyncMock(return_value=state)
    runner.run_single_step = AsyncMock(return_value=state)

    await runner.resolve_step("r1", 2, "rerun")

    updated = rm.load_state("r1")
    assert updated.bom_deepen_count == 1
    runner._run_agent_internal.assert_awaited_once_with("r1", step=1)
    runner.run_single_step.assert_awaited_once_with("r1", step=2)


class TestAgent3DeepenHint:
    @pytest.mark.asyncio
    async def test_less_than_two_bottlenecks_sets_hint(self, minimal_config_dict, filled_pipeline_state_dict):
        from manus.steps.agent3_bottleneck import run_agent3

        state = {**filled_pipeline_state_dict, "bottlenecks": []}
        state.pop("component_node", None)
        with patch("manus.steps.agent3_bottleneck.fetch_agent_rag_context", return_value=("", [])):
            with patch("manus.steps.agent3_bottleneck.invoke_llm_json", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {"bottlenecks": [], "ripple_notes": ""}
                result = await run_agent3(state, config=minimal_config_dict)
        hints = result.get("approval_hints") or {}
        assert hints.get("suggest_deepen_bom") is True or result.get("suggest_deepen_bom") is True
