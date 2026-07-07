# -*- coding: utf-8 -*-
"""步骤编号约定测试（SPEC v1.4.1：step 0～5，agent = step + 1）。"""

from __future__ import annotations

import pytest

from manus.pipeline.constants import (
    AGENT_COUNT,
    MAX_STEP,
    MIN_STEP,
    agent_to_step,
    step_to_agent,
    validate_step,
)


class TestStepConstants:
    def test_step_range(self):
        assert MIN_STEP == 0
        assert MAX_STEP == 5
        assert AGENT_COUNT == 6

    @pytest.mark.parametrize("step,agent", [(0, 1), (1, 2), (5, 6)])
    def test_step_agent_mapping(self, step: int, agent: int):
        assert step_to_agent(step) == agent
        assert agent_to_step(agent) == step

    def test_invalid_step_raises(self):
        with pytest.raises(ValueError):
            validate_step(6)
        with pytest.raises(ValueError):
            validate_step(-1)

    def test_invalid_agent_raises(self):
        with pytest.raises(ValueError):
            agent_to_step(0)
        with pytest.raises(ValueError):
            agent_to_step(7)
