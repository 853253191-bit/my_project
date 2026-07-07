# -*- coding: utf-8 -*-
"""决策门与 approval_hints（SPEC §3.2.1 / §3.2.2）。"""

from __future__ import annotations

from manus.pipeline.state import PipelineState
from manus.schemas.models import ApprovalHints, ChecklistGateResult


def gate_outlook(state: PipelineState) -> ApprovalHints:
    result = state.gate_outlook_result or "continue"
    hints = ApprovalHints()
    if result == "stop":
        hints.block_proceed = True
        hints.outlook_stop = True
        hints.messages.append("终端需求 outlook=stop，建议重选方向或重跑")
    elif result == "uncertain":
        hints.outlook_uncertain = True
        hints.messages.append("终端需求 outlook=uncertain，请人工确认是否继续拆解")
    return hints


def gate_checklist(state: PipelineState, gate: ChecklistGateResult) -> ApprovalHints:
    hints = ApprovalHints()
    if gate.result == "hard_fail":
        hints.checklist_hard_fail = True
        hints.messages.append(f"检查清单硬项未通过: {', '.join(gate.failed_hard_ids)}")
    if state.confidence == "low":
        hints.confidence_low = True
    return hints


def build_approval_hints(
    state: PipelineState,
    step: int,
    *,
    degraded: bool = False,
    suggest_deepen_bom: bool = False,
    extra: ApprovalHints | None = None,
) -> ApprovalHints:
    hints = extra or ApprovalHints()
    if degraded:
        hints.degraded = True
        hints.messages.append("当步 Agent 降级完成，请确认是否重跑")
    if suggest_deepen_bom:
        hints.suggest_deepen_bom = True
        hints.messages.append("瓶颈数量不足，建议 rerun 加深 BOM 拆解")
    if state.errors:
        for err in state.errors:
            if "degraded" in err.lower():
                hints.degraded = True
    return hints
