# -*- coding: utf-8 -*-
"""步骤编号常量（SPEC v1.4.1）。"""

from __future__ import annotations

MIN_STEP = 0
MAX_STEP = 5
AGENT_COUNT = 6

AGENT_NAMES = [
    "NewsCollector",
    "ComponentMapper",
    "BottleneckAnalyzer",
    "QuantValidator",
    "SupplierScreener",
    "ReportWriter",
]

AGENT_STEP_MODULES = [
    "manus.steps.agent1_news",
    "manus.steps.agent2_components",
    "manus.steps.agent3_bottleneck",
    "manus.steps.agent4_quant",
    "manus.steps.agent5_supplier",
    "manus.steps.agent6_report",
]


def validate_step(step: int) -> int:
    if step < MIN_STEP or step > MAX_STEP:
        raise ValueError(f"step 必须在 {MIN_STEP}～{MAX_STEP} 之间，收到: {step}")
    return step


def step_to_agent(step: int) -> int:
    validate_step(step)
    return step + 1


def agent_to_step(agent: int) -> int:
    if agent < 1 or agent > AGENT_COUNT:
        raise ValueError(f"agent 必须在 1～{AGENT_COUNT} 之间，收到: {agent}")
    return agent - 1
