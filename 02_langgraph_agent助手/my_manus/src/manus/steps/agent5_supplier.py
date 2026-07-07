# -*- coding: utf-8 -*-
"""Agent5：A 股主板供应商筛选。"""

from __future__ import annotations

from typing import Any

from manus.llm import invoke_llm_json
from manus.pipeline.progress import emit_progress
from manus.schemas.models import Financials, SupplierProfile
from manus.tools.a_share_lookup import lookup_for_state
from manus.tools.finance_lookup import FinanceLookupError, finance_lookup
from manus.tools.supplier_normalize import (
    SUPPLIER_JSON_SCHEMA_HINT,
    default_bottleneck_id_from_state,
    normalize_supplier_dict,
    parse_supplier_profiles,
)
from manus.tools.supplier_screen import filter_suppliers

from manus.rag.context import bottleneck_hint_from_state, fetch_agent_rag_context

_TUSHARE_SOURCE_IDS = ("tushare-concept", "tushare-industry", "tushare-name", "bn-unknown")


def _merge_supplier_raws(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """多来源合并，按 ticker 去重。"""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for batch in sources:
        for item in batch:
            norm = normalize_supplier_dict(item)
            ticker = (norm.get("ticker") or "").strip().upper()
            name = (norm.get("company_name") or "").strip()
            key = ticker or name
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(norm)
    return merged


def _enrich_financials(
    suppliers: list[SupplierProfile],
    cache_ttl_sec: int,
    config: dict[str, Any] | Any,
) -> tuple[list[SupplierProfile], list[str]]:
    enriched: list[SupplierProfile] = []
    errors: list[str] = []
    for sp in suppliers:
        if not sp.ticker:
            enriched.append(sp)
            continue
        try:
            fin = finance_lookup(sp.ticker, cache_ttl_sec=cache_ttl_sec, config=config)
            enriched.append(sp.model_copy(update={"financials": fin}))
        except FinanceLookupError as exc:
            errors.append(f"finance_lookup_{sp.ticker}: {exc}")
            enriched.append(
                sp.model_copy(
                    update={
                        "financials": Financials(
                            unavailable=True,
                            unavailable_reason=str(exc),
                        )
                    }
                )
            )
    return enriched, errors


def _build_agent5_system_prompt() -> str:
    return (
        "你是 A 股主板供应商分析师。"
        "仅推荐沪深主板上市公司（600/601/603/605/000/001/002 开头），"
        "禁止科创板 688、创业板 300、北交所及 ST/*ST。"
        "必须严格使用下方 JSON 字段名，禁止使用 code/name 等别名。"
        + SUPPLIER_JSON_SCHEMA_HINT
    )


def _build_agent5_user_prompt(
    state: dict[str, Any],
    rag_text: str,
    tushare_context: str,
    bom_fallback: bool,
    a_share_from_agent4: list[dict[str, Any]],
) -> str:
    default_bn = default_bottleneck_id_from_state(state)
    return (
        f"{rag_text}\n\n"
        f"{tushare_context}\n\n"
        f"bom_fallback_used={bom_fallback}\n"
        f"default_bottleneck_id={default_bn}\n"
        f"a_share_candidates_from_agent4={a_share_from_agent4}\n"
        f"component_node={state.get('component_node')}\n"
        f"bottlenecks={state.get('bottlenecks')}\n"
        f"validations={state.get('validations')}\n\n"
        "请结合 Tushare 检索结果与产业链 bottlenecks，"
        "为每个 bottleneck_id 推荐 1～3 家最相关的主板供应商。"
        "优先从 Tushare 候选中挑选并补充 screening_rationale；"
        "若 Tushare 无结果，可基于你的 A 股产业链知识推荐，但 ticker 必须准确。"
    )


async def run_agent5(state: dict[str, Any], config: dict[str, Any] | Any) -> dict[str, Any]:
    screen_cfg = config.get("supplier_screen", {}) if isinstance(config, dict) else {}
    finance_cfg = config.get("finance", {}) if isinstance(config, dict) else {}
    min_days = int(screen_cfg.get("min_listing_days", 60))
    cache_ttl = int(finance_cfg.get("cache_ttl_sec", 3600))
    hint = bottleneck_hint_from_state(state)
    bom_fallback = bool(state.get("bom_fallback_used"))
    a_share_from_agent4 = list(state.get("a_share_candidates") or [])
    default_bn = default_bottleneck_id_from_state(state)

    emit_progress("Tushare 检索 A 股概念/行业/公司…")
    tushare_raw, tushare_context, tushare_errors = lookup_for_state(state, config=config)
    if tushare_raw:
        emit_progress(f"Tushare 命中 {len(tushare_raw)} 家主板候选")

    emit_progress("检索案例库辅助供应商筛选…")
    rag_text, rag_errors = fetch_agent_rag_context(
        "agent5", config, query_extra=hint, bottleneck_name=hint, include_cases=True
    )

    llm_raw: list[dict[str, Any]] = []
    llm_errors: list[str] = []
    try:
        emit_progress("调用大模型推荐 A 股主板供应商…")
        data = await invoke_llm_json(
            config,
            [
                {"role": "system", "content": _build_agent5_system_prompt()},
                {
                    "role": "user",
                    "content": _build_agent5_user_prompt(
                        state, rag_text, tushare_context, bom_fallback, a_share_from_agent4
                    ),
                },
            ],
        )
        llm_raw = list(data.get("suppliers") or [])
    except Exception as exc:
        llm_errors.append(f"agent5_llm_failed: {exc}")

    merged = _merge_supplier_raws(tushare_raw, a_share_from_agent4, llm_raw)
    for item in merged:
        if item.get("bottleneck_id") in _TUSHARE_SOURCE_IDS:
            item["bottleneck_id"] = default_bn

    parse_errors: list[str] = []
    candidates, parse_errors = parse_supplier_profiles(merged, default_bottleneck_id=default_bn)

    eligible, filter_errors, excluded = filter_suppliers(
        candidates,
        bottleneck_name=state.get("bottlenecks", [{}])[0].get("bottleneck_name", "")
        if state.get("bottlenecks")
        else hint,
        min_listing_days=min_days,
    )

    if eligible:
        emit_progress(f"为 {len(eligible)} 家标的查询 Tushare 财务摘要…")
    eligible, fin_errors = _enrich_financials(eligible, cache_ttl_sec=cache_ttl, config=config)

    all_errors = (
        list(state.get("errors") or [])
        + tushare_errors
        + rag_errors
        + llm_errors
        + parse_errors
        + filter_errors
        + fin_errors
    )

    return {
        "suppliers": [s.model_dump(mode="json") for s in eligible],
        "suppliers_excluded": excluded,
        "errors": all_errors,
        "step_output_summary": f"筛选合格 A 股主板供应商 {len(eligible)} 家（Tushare {len(tushare_raw)} + LLM 合并）",
        "rag_contexts": {
            **(state.get("rag_contexts") or {}),
            "agent5": rag_text,
            "agent5_tushare": tushare_context,
        },
    }
