# -*- coding: utf-8 -*-
"""Pydantic 模型，对齐 SPEC 附录 A。"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class NewsItem(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    heat_score: float = Field(ge=0, le=1)
    relevance_tags: list[str] = Field(min_length=1)
    hardware_focus: bool
    hardware_tags: list[str] = Field(default_factory=list)
    research_hint: str
    why_selected: str = ""


class TerminalDemand(BaseModel):
    description: str
    outlook_2_3y: Literal["continue", "stop", "uncertain"]
    backing: str


class ComponentItem(BaseModel):
    name: str
    category: Literal["core_module", "interconnect", "power_thermal", "materials_equipment"]
    value_share: Literal["high", "medium", "low"]
    growth_driver: str
    upstream_hints: list[str] = Field(default_factory=list)


class HorizontalBranch(BaseModel):
    type: Literal["isomorphic", "upstream_material", "substitution"]
    node: str
    rationale: str


class ComponentNode(BaseModel):
    news_id: str
    decomposition_depth: int = Field(ge=1, le=6)
    terminal_demand: TerminalDemand
    components: list[ComponentItem] = Field(min_length=1)
    horizontal_branches: list[HorizontalBranch] = Field(min_length=1)


class BottleneckTraits(BaseModel):
    mandatory: Literal["true", "false", "unknown"]
    oligopoly: Literal["true", "false", "unknown"]
    slow_expansion: Literal["true", "false", "unknown"]
    low_coverage: Literal["true", "false", "unknown"]


class BottleneckItem(BaseModel):
    id: str
    component: str
    bottleneck_name: str
    layer: Literal["module", "device", "material", "process", "equipment"]
    traits: BottleneckTraits
    mismatch_hypothesis: str
    evidence: list[str] = Field(min_length=1)
    supplier_count_est: int | None = Field(default=None, ge=1)
    expansion_cycle_months: int | None = Field(default=None, ge=0)


class SupplyTest(BaseModel):
    architecture_change_required: bool
    switching_time_months: int = Field(ge=0)
    hoarding_signals: str
    switching_cost: Literal["low", "medium", "high", "extreme"]


class ChecklistPassItem(BaseModel):
    item: str
    passed: bool
    note: str = ""


class ValidationReport(BaseModel):
    bottleneck_id: str
    irreplaceability_score: int = Field(ge=1, le=5)
    supply_test: SupplyTest
    assumptions: list[str] = Field(min_length=1)
    checklist_pass: list[ChecklistPassItem] = Field(default_factory=list)
    supply_capacity: str = ""
    demand_estimate: str = ""
    gap_ratio: float | None = Field(default=None, ge=0, le=1)
    duration_quarters: int | None = Field(default=None, ge=0)
    price_elasticity: str = ""
    counter_evidence: list[str] = Field(default_factory=list)


class Financials(BaseModel):
    revenue: str = ""
    gross_margin: str = ""
    cash_flow: str = ""
    debt: str = ""
    unavailable: bool = False
    unavailable_reason: str = ""


class SupplierProfile(BaseModel):
    bottleneck_id: str
    company_name: str
    ticker: str = ""
    market: Literal["CN"] = "CN"
    listing_board: Literal["main"] = "main"
    is_st: bool = False
    business_focus_pct: float = Field(ge=0, le=100)
    coverage_level: Literal["high", "medium", "low"]
    risks: list[str] = Field(min_length=1)
    catalysts: list[str] = Field(default_factory=list)
    market_cap: str = ""
    revenue_mix: str = ""
    financials: Financials | None = None
    valuation_note: str = ""
    industry_direction: str = ""
    screening_rationale: str = ""

    @field_validator("is_st")
    @classmethod
    def reject_st(cls, v: bool) -> bool:
        if v:
            raise ValueError("suppliers 内 is_st 必须为 false")
        return v

    @field_validator("listing_board")
    @classmethod
    def reject_non_main(cls, v: str) -> str:
        if v != "main":
            raise ValueError("listing_board 仅允许 main")
        return v


class RedTeamReport(BaseModel):
    alternative_routes: list[str] = Field(min_length=1)
    falsification_data_needed: list[str] = Field(min_length=3)
    supply_response_risk: str
    needs_human_review: bool


class ChecklistHardItem(BaseModel):
    id: Literal["H1_terminal_demand", "H2_bom_depth", "H3_supply_test", "H4_quantitative"]
    passed: bool
    note: str = ""


class ChecklistSoftItem(BaseModel):
    item: str
    passed: bool
    note: str = ""


class ChecklistGateResult(BaseModel):
    result: Literal["pass", "hard_fail", "soft_fail"]
    hard_items: list[ChecklistHardItem]
    soft_items: list[ChecklistSoftItem] = Field(default_factory=list)
    failed_hard_ids: list[str] = Field(default_factory=list)
    auto_retry_attempted: bool = False


class ApprovalHints(BaseModel):
    block_proceed: bool = False
    outlook_uncertain: bool = False
    outlook_stop: bool = False
    checklist_hard_fail: bool = False
    confidence_low: bool = False
    degraded: bool = False
    suggest_deepen_bom: bool = False
    messages: list[str] = Field(default_factory=list)


class SupplierExcluded(BaseModel):
    ticker: str
    reason: str


class RunDetail(BaseModel):
    run_id: str
    run_date: str
    status: Literal["pending", "running", "awaiting_step_approval", "completed", "failed"]
    phase: Literal["collect", "research"] = "collect"
    pending_approval_step: int | None = Field(default=None, ge=0, le=5)
    step_output_summary: str | None = None
    approval_hints: ApprovalHints | None = None
    gate_outlook_result: Literal["continue", "stop", "uncertain"] | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    agent6_mode: Literal["generate", "regenerate"] = "generate"
    rerun_from_step: int | None = None
    news_items: list[NewsItem] = Field(default_factory=list)
    selected_news_id: str | None = None
    selected_news_item: NewsItem | None = None
    component_node: ComponentNode | None = None
    bottlenecks: list[BottleneckItem] = Field(default_factory=list)
    validations: list[ValidationReport] = Field(default_factory=list)
    red_team: RedTeamReport | None = None
    checklist_gate: ChecklistGateResult | None = None
    suppliers: list[SupplierProfile] = Field(default_factory=list)
    suppliers_excluded: list[SupplierExcluded] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    final_report_md: str = ""
    report_output_path: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class StepResolveRequest(BaseModel):
    action: Literal["proceed", "rerun", "change_direction"]
    news_id: str | None = None


class StepApprovalView(BaseModel):
    run_id: str
    step: int = Field(ge=0, le=5)
    agent: int = Field(ge=1, le=6)
    agent_name: str
    status: Literal["awaiting_step_approval"] = "awaiting_step_approval"
    step_output_summary: str = ""
    approval_hints: ApprovalHints = Field(default_factory=ApprovalHints)
    output: dict[str, Any] = Field(default_factory=dict)
