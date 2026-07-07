# -*- coding: utf-8 -*-
"""PipelineState 与初始状态（SPEC §3.1）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from manus.schemas.models import (
    ApprovalHints,
    BottleneckItem,
    ChecklistGateResult,
    ComponentNode,
    NewsItem,
    RedTeamReport,
    SupplierExcluded,
    SupplierProfile,
    ValidationReport,
)


class PipelineState(BaseModel):
    run_id: str
    run_date: str
    phase: Literal["collect", "research"] = "collect"
    status: Literal["pending", "running", "awaiting_step_approval", "completed", "failed"] = "pending"
    pending_approval_step: int | None = None
    step_output_summary: str | None = None
    approval_hints: ApprovalHints | None = None
    news_items: list[NewsItem] = Field(default_factory=list)
    selected_news_id: str | None = None
    selected_news_item: NewsItem | None = None
    component_node: ComponentNode | None = None
    gate_outlook_result: Literal["continue", "stop", "uncertain"] | None = None
    bottlenecks: list[BottleneckItem] = Field(default_factory=list)
    ripple_notes: str = ""
    validations: list[ValidationReport] = Field(default_factory=list)
    red_team: RedTeamReport | None = None
    checklist_gate: ChecklistGateResult | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    suppliers: list[SupplierProfile] = Field(default_factory=list)
    suppliers_excluded: list[SupplierExcluded] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    final_report_md: str = ""
    report_output_path: str | None = None
    agent6_mode: Literal["generate", "regenerate"] = "generate"
    rerun_from_step: int | None = None
    bom_deepen_count: int = 0
    bom_fallback_used: bool = False
    a_share_candidates: list[dict[str, Any]] = Field(default_factory=list)
    rag_contexts: dict[str, str] = Field(default_factory=dict)
    created_at: str | None = None
    completed_at: str | None = None

    model_config = {"validate_assignment": False}


def create_initial_state(run_id: str | None = None, run_date: str | None = None) -> PipelineState:
    now = datetime.now(timezone.utc).isoformat()
    return PipelineState(
        run_id=run_id or f"run-{uuid4().hex[:12]}",
        run_date=run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        status="pending",
        created_at=now,
    )


def state_to_run_detail(state: PipelineState) -> dict[str, Any]:
    return state.model_dump(mode="json")
