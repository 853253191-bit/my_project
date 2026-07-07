# -*- coding: utf-8 -*-
"""Agent RAG 上下文注入（strategy + cases）。"""

from __future__ import annotations

from typing import Any

from manus.config import AppConfig, config_to_dict, load_config
from manus.rag.cases_chunk import format_cases_context
from manus.rag.chunk import format_rag_context
from manus.rag.retriever import StrategyRetriever, build_fallback_context
from manus.rag.store import get_store

CASES_QUERY_TEMPLATES: dict[str, str] = {
    "agent3": "{bottleneck_name} supply chain bottleneck case study",
    "agent5": "{bottleneck_name} supplier company financial analysis",
}


def _cfg_dict(config: AppConfig | dict[str, Any] | None) -> dict[str, Any]:
    if config is None:
        return load_config().model_dump()
    if isinstance(config, dict):
        return config
    return config_to_dict(config)


def fetch_strategy_context(
    agent_key: str,
    config: AppConfig | dict[str, Any] | None = None,
    query_extra: str = "",
) -> tuple[str, list[str]]:
    """检索 strategy collection，空库时 fallback。"""
    cfg = _cfg_dict(config)
    store = get_store(cfg, collection=cfg.get("rag", {}).get("collection", "strategy"))
    errors: list[str] = []
    if store is None:
        errors.append("RAG_EMPTY: Chroma 未初始化，使用 fallback 策略片段")
        return format_rag_context([build_fallback_context()]), errors

    retriever = StrategyRetriever(store=store, config=cfg.get("rag", {}))
    chunks, rag_errors = retriever.retrieve_with_fallback(agent_key, query_extra=query_extra)
    errors.extend(rag_errors)
    text = format_rag_context(chunks, max_context_chars=int(cfg.get("rag", {}).get("max_context_chars", 6000)))
    return text, errors


def fetch_cases_context(
    bottleneck_name: str,
    agent_key: str,
    config: AppConfig | dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """检索 cases collection（Agent3 / Agent5）。"""
    cfg = _cfg_dict(config)
    cases_coll = cfg.get("rag", {}).get("cases_collection", "cases")
    store = get_store(cfg, collection=cases_coll)
    errors: list[str] = []
    if store is None:
        errors.append("CASES_EMPTY: 案例库未 ingest")
        return "", errors

    template = CASES_QUERY_TEMPLATES.get(agent_key, "{bottleneck_name}")
    query = template.format(bottleneck_name=bottleneck_name or "supply chain")
    retriever = StrategyRetriever(store=store, config=cfg.get("rag", {}))
    chunks, scores = retriever.retrieve(agent_key, query_extra=query)
    if not chunks:
        errors.append(f"CASES_EMPTY: 未检索到与 {bottleneck_name} 相关的案例")
        return "", errors

    text = format_cases_context(
        chunks,
        max_context_chars=int(cfg.get("rag", {}).get("max_context_chars", 6000)),
    )
    return text, errors


def fetch_agent_rag_context(
    agent_key: str,
    config: AppConfig | dict[str, Any] | None = None,
    *,
    query_extra: str = "",
    bottleneck_name: str = "",
    include_cases: bool = False,
) -> tuple[str, list[str]]:
    """合并 strategy + 可选 cases 上下文。"""
    parts: list[str] = []
    errors: list[str] = []

    strategy_text, strategy_errors = fetch_strategy_context(agent_key, config, query_extra=query_extra)
    parts.append(strategy_text)
    errors.extend(strategy_errors)

    if include_cases and agent_key in ("agent3", "agent5"):
        cases_text, cases_errors = fetch_cases_context(bottleneck_name, agent_key, config)
        if cases_text:
            parts.append(cases_text)
        errors.extend(cases_errors)

    return "\n\n".join(p for p in parts if p), errors


def bottleneck_hint_from_state(state: dict[str, Any]) -> str:
    """从 state 推断案例检索用的瓶颈/组件名。"""
    for bn in state.get("bottlenecks") or []:
        name = bn.get("bottleneck_name") if isinstance(bn, dict) else getattr(bn, "bottleneck_name", "")
        if name:
            return name
    node = state.get("component_node") or {}
    for comp in node.get("components") or []:
        name = comp.get("name") if isinstance(comp, dict) else getattr(comp, "name", "")
        if name:
            return name
    news = state.get("selected_news_item") or {}
    return news.get("title", "AI hardware supply chain") if isinstance(news, dict) else "AI hardware supply chain"
