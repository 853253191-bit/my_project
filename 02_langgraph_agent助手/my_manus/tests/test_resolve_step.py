# -*- coding: utf-8 -*-
"""resolve_step 与 state 规范化测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from manus.pipeline.normalize import normalize_state_models
from manus.pipeline.runner import PipelineRunner
from manus.pipeline.state import create_initial_state
from manus.schemas.models import NewsItem


@pytest.mark.asyncio
async def test_resolve_step0_when_running_with_pending_zero(tmp_path):
    """API 将 status=running 且 pending=0 时，background resolve 应能继续。"""
    from manus.api.run_manager import RunManager

    rm = RunManager(tmp_path)
    state = create_initial_state(run_id="r1", run_date="2026-07-07")
    state.status = "running"
    state.pending_approval_step = 0
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
    rm.save_state(state)

    runner = PipelineRunner(config={"workflow": {"step_approval_required": True}}, run_manager=rm)
    runner.run_single_step = AsyncMock(
        return_value=create_initial_state(run_id="r1", run_date="2026-07-07")
    )

    await runner.resolve_step("r1", 0, "proceed", news_id="news-1")
    runner.run_single_step.assert_awaited_once_with("r1", step=1)


def test_normalize_dict_news_items():
    state = create_initial_state(run_id="r1", run_date="2026-07-07")
    state.news_items = [{"id": "n1", "title": "t", "summary": "s", "source": "x", "url": "u",
                         "published_at": "2026-07-07", "heat_score": 0.5, "relevance_tags": ["AI"],
                         "hardware_focus": True, "research_hint": "h"}]
    normalize_state_models(state)
    assert isinstance(state.news_items[0], NewsItem)
