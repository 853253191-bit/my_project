# -*- coding: utf-8 -*-
"""PipelineState 字段规范化。"""

from __future__ import annotations

from manus.pipeline.state import PipelineState
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


def _coerce(model_cls, value):
    if value is None:
        return None
    if isinstance(value, dict):
        return model_cls.model_validate(value)
    return value


def _coerce_list(model_cls, items: list) -> list:
    return [_coerce(model_cls, item) for item in items]


def normalize_state_models(state: PipelineState) -> PipelineState:
    """将 agent 写入的 dict 字段还原为 Pydantic 模型，避免 model_dump 报错。"""
    state.approval_hints = _coerce(ApprovalHints, state.approval_hints)
    state.selected_news_item = _coerce(NewsItem, state.selected_news_item)
    if state.news_items:
        state.news_items = _coerce_list(NewsItem, state.news_items)
    state.component_node = _coerce(ComponentNode, state.component_node)
    if state.bottlenecks:
        state.bottlenecks = _coerce_list(BottleneckItem, state.bottlenecks)
    if state.validations:
        state.validations = _coerce_list(ValidationReport, state.validations)
    state.red_team = _coerce(RedTeamReport, state.red_team)
    state.checklist_gate = _coerce(ChecklistGateResult, state.checklist_gate)
    if state.suppliers:
        state.suppliers = _coerce_list(SupplierProfile, state.suppliers)
    if state.suppliers_excluded:
        state.suppliers_excluded = _coerce_list(SupplierExcluded, state.suppliers_excluded)
    return state
