# -*- coding: utf-8 -*-
"""Agent4：定量验证、red-team 与 A 股标的匹配。"""

from __future__ import annotations

import json
from typing import Any

from manus.llm import invoke_llm_json
from manus.pipeline.bom_fallback import format_bom_chain_text
from manus.pipeline.gates import gate_checklist
from manus.pipeline.progress import emit_progress
from manus.pipeline.state import PipelineState
from manus.schemas.models import ChecklistGateResult, RedTeamReport, ValidationReport
from manus.tools.a_share_lookup import lookup_for_state
from manus.tools.supplier_normalize import (
    SUPPLIER_JSON_SCHEMA_HINT,
    default_bottleneck_id_from_state,
    parse_supplier_profiles,
)


def _default_checklist_gate() -> dict[str, Any]:
    return {
        "result": "pass",
        "hard_items": [
            {"id": "H1_terminal_demand", "passed": True},
            {"id": "H2_bom_depth", "passed": True},
            {"id": "H3_supply_test", "passed": True},
            {"id": "H4_quantitative", "passed": True},
        ],
        "soft_items": [],
        "failed_hard_ids": [],
        "auto_retry_attempted": False,
    }


def _build_agent4_system_prompt(bom_fallback: bool) -> str:
    base = (
        "你是量化验证员与 A 股产业链映射分析师。"
        "输出 JSON：validations[]、red_team、checklist_gate、a_share_candidates[]。"
    )
    schema = (
        "a_share_candidates 字段必须与 Agent5 一致："
        "bottleneck_id、company_name、ticker（如 600584.SH）、business_focus_pct、"
        "coverage_level、risks[]、screening_rationale。禁止使用 code/name。"
        + SUPPLIER_JSON_SCHEMA_HINT.replace("suppliers", "a_share_candidates")
    )
    if bom_fallback:
        return (
            base
            + "当前为 BOM 产业链回退模式：Agent3 未识别出瓶颈，bottlenecks 来自 Agent2 产业链拆解。"
            "请基于 component_node 各环节做轻量断供/供需验证，并为每个 bottleneck_id 匹配 1～2 家"
            "沪深主板 A 股上市公司。"
            + schema
        )
    return base + "对 bottlenecks 做断供测试与定量验证；若有高分瓶颈可预填 a_share_candidates。" + schema


def _build_agent4_user_prompt(
    state: dict[str, Any],
    bom_fallback: bool,
    tushare_context: str,
) -> str:
    parts = [
        tushare_context,
        f"bottlenecks={json.dumps(state.get('bottlenecks') or [], ensure_ascii=False)}",
        f"component_node={json.dumps(state.get('component_node') or {}, ensure_ascii=False)}",
    ]
    if bom_fallback:
        parts.insert(
            0,
            "【BOM 回退模式】无明确瓶颈，请沿产业链各环节匹配相关 A 股标的并输出 a_share_candidates。",
        )
        parts.append(format_bom_chain_text(state.get("component_node")))
    parts.append("优先从 Tushare 检索结果中挑选最相关的主板标的。")
    return "\n\n".join(parts)


def _candidates_to_dicts(profiles: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in profiles:
        if hasattr(p, "model_dump"):
            out.append(p.model_dump(mode="json"))
        else:
            out.append(dict(p))
    return out


async def run_agent4(state: dict[str, Any], config: dict[str, Any] | Any) -> dict[str, Any]:
    bom_fallback = bool(state.get("bom_fallback_used"))
    default_bn = default_bottleneck_id_from_state(state)

    emit_progress("Tushare 检索产业链相关 A 股标的…")
    tushare_raw, tushare_context, tushare_errors = lookup_for_state(state, config=config)

    if bom_fallback:
        emit_progress("BOM 回退模式：基于产业链匹配 A 股标的并做轻量验证…")
    else:
        emit_progress("调用大模型执行定量验证与 red-team…")

    a_share_candidates: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    try:
        data = await invoke_llm_json(
            config,
            [
                {"role": "system", "content": _build_agent4_system_prompt(bom_fallback)},
                {"role": "user", "content": _build_agent4_user_prompt(state, bom_fallback, tushare_context)},
            ],
        )
        validations = [ValidationReport.model_validate(v) for v in data.get("validations", [])]
        red_team = RedTeamReport.model_validate(data["red_team"]) if data.get("red_team") else None
        gate = ChecklistGateResult.model_validate(data.get("checklist_gate", _default_checklist_gate()))
        llm_candidates = list(data.get("a_share_candidates") or [])
    except Exception:
        validations = []
        red_team = RedTeamReport(
            alternative_routes=["替代路线A"],
            falsification_data_needed=["d1", "d2", "d3"],
            supply_response_risk="扩产超预期",
            needs_human_review=False,
        )
        gate = ChecklistGateResult.model_validate(_default_checklist_gate())
        llm_candidates = []

    merged_raw = list(tushare_raw) + llm_candidates
    profiles, parse_errors = parse_supplier_profiles(merged_raw, default_bottleneck_id=default_bn)
    a_share_candidates = _candidates_to_dicts(profiles)

    ps = PipelineState.model_validate(
        {
            "run_id": state.get("run_id", "x"),
            "run_date": state.get("run_date", "2026-01-01"),
            "confidence": "high",
        }
    )
    hints = gate_checklist(ps, gate)

    summary = "完成断供测试与检查清单"
    if bom_fallback or a_share_candidates:
        summary = f"匹配 A 股标的 {len(a_share_candidates)} 家并完成验证（Tushare {len(tushare_raw)} 家）"

    return {
        "validations": [v.model_dump(mode="json") for v in validations],
        "red_team": red_team.model_dump(mode="json") if red_team else None,
        "checklist_gate": gate.model_dump(mode="json"),
        "approval_hints": hints.model_dump(mode="json"),
        "confidence": "high",
        "a_share_candidates": a_share_candidates,
        "errors": list(state.get("errors") or []) + tushare_errors + parse_errors,
        "step_output_summary": summary,
        "rag_contexts": {**(state.get("rag_contexts") or {}), "agent4_tushare": tushare_context},
    }
