# -*- coding: utf-8 -*-
"""Agent 步骤契约测试（P1 最小可跑通）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from manus.pipeline.constants import AGENT_STEP_MODULES, step_to_agent


class TestAgentStepRegistry:
    def test_six_steps_registered(self):
        assert len(AGENT_STEP_MODULES) == 6

    @pytest.mark.parametrize("step", range(6))
    def test_each_step_maps_to_agent(self, step: int):
        assert step_to_agent(step) == step + 1
        assert f"agent{step + 1}" in AGENT_STEP_MODULES[step]


class TestAgent1Contract:
    @pytest.mark.asyncio
    async def test_returns_max_five_news(self, minimal_config_dict):
        from manus.steps.agent1_news import run_agent1

        with patch("manus.steps.agent1_news.search_news", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"id": f"n{i}", "title": f"t{i}"} for i in range(10)]
            result = await run_agent1({}, config=minimal_config_dict)
        items = result.get("news_items", [])
        assert len(items) <= 5
