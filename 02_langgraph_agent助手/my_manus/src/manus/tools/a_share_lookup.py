# -*- coding: utf-8 -*-
"""Tushare 板块/概念检索 A 股主板标的。"""

from __future__ import annotations

import re
from typing import Any

from manus.tools.supplier_normalize import format_a_share_ticker, normalize_supplier_dict
from manus.tools.supplier_screen import is_eligible_a_share_main
from manus.tools.tushare_client import TushareError, get_pro_api, load_concepts, load_stock_basic

# 产业链关键词扩展
_KEYWORD_EXPAND: dict[str, list[str]] = {
    "HBM": ["HBM", "存储芯片", "先进封装", "半导体"],
    "存储": ["存储芯片", "半导体", "DRAM", "NAND"],
    "半导体": ["半导体", "芯片", "集成电路"],
    "先进封装": ["先进封装", "封装", "Chiplet"],
    "CPO": ["CPO", "光模块", "光通信"],
    "光模块": ["光模块", "光通信", "CPO"],
    "PCB": ["PCB", "印制电路板", "算力"],
    "IDC": ["IDC", "数据中心", "算力"],
    "算力": ["算力", "人工智能", "数据中心"],
    "AI": ["人工智能", "算力", "服务器"],
}

# 从文本中扫描的固定产业词
_INDUSTRY_TERMS = (
    "CPO",
    "PCB",
    "HBM",
    "光模块",
    "存储",
    "半导体",
    "先进封装",
    "IDC",
    "算力",
    "硅光",
    "DRAM",
    "NAND",
    "封装",
    "互连",
    "铜缆",
    "人工智能",
)

_COMPANY_NAME_PATTERN = re.compile(
    r"[\u4e00-\u9fff]{2,10}(?:科技|电子|通信|股份|集团|光电|材料|微|电路|信息)"
)


def _clean_keyword(text: str) -> str:
    text = re.sub(r"[#【】\[\]()（）]", "", text).strip()
    if len(text) > 20:
        return ""
    return text


def extract_chain_keywords(state: dict[str, Any]) -> list[str]:
    """从 pipeline state 提取产业链检索关键词。"""
    keywords: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        text = _clean_keyword(str(text or ""))
        if len(text) >= 2 and text not in seen:
            seen.add(text)
            keywords.append(text)

    news = state.get("selected_news_item") or {}
    title = news.get("title", "") if isinstance(news, dict) else ""
    summary = news.get("summary", "") if isinstance(news, dict) else ""
    full_text = f"{title} {summary}"

    for term in _INDUSTRY_TERMS:
        if term in full_text:
            add(term)

    for token in re.split(r"[+、|｜/\\s,，:：]+", title):
        add(token)

    for name in _COMPANY_NAME_PATTERN.findall(full_text):
        add(name)

    node = state.get("component_node") or {}
    if isinstance(node, dict):
        for comp in node.get("components") or []:
            if isinstance(comp, dict):
                add(comp.get("name", ""))
                for hint in comp.get("upstream_hints") or []:
                    add(str(hint))
        for br in node.get("horizontal_branches") or []:
            if isinstance(br, dict):
                add(br.get("node", ""))

    for bn in state.get("bottlenecks") or []:
        if isinstance(bn, dict):
            add(bn.get("bottleneck_name", ""))
            add(bn.get("component", ""))

    expanded: list[str] = []
    for kw in keywords:
        expanded.append(kw)
        for key, aliases in _KEYWORD_EXPAND.items():
            if key in kw or kw in key:
                for alias in aliases:
                    if alias not in seen:
                        seen.add(alias)
                        expanded.append(alias)
    return expanded[:24]


def _append_candidate(
    results: list[dict[str, Any]],
    seen_tickers: set[str],
    *,
    ts_code: str,
    name: str,
    rationale: str,
    source_id: str,
    max_total: int,
) -> bool:
    ticker = ts_code if "." in ts_code else format_a_share_ticker(ts_code)
    ok, _ = is_eligible_a_share_main(ticker, name)
    if not ok or ticker in seen_tickers:
        return len(results) >= max_total
    seen_tickers.add(ticker)
    results.append(
        normalize_supplier_dict(
            {
                "ticker": ticker,
                "company_name": name,
                "screening_rationale": rationale,
                "coverage_level": "medium",
                "business_focus_pct": 50.0,
                "risks": ["板块/行业匹配，需核对主业占比"],
            },
            default_bottleneck_id=source_id,
        )
    )
    return len(results) >= max_total


def search_main_board_by_keywords(
    keywords: list[str],
    config: dict[str, Any] | Any | None = None,
    *,
    max_concepts: int = 4,
    max_stocks_per_source: int = 8,
    max_total: int = 30,
) -> tuple[list[dict[str, Any]], list[str]]:
    """用 Tushare 概念/行业/名称检索主板标的。"""
    errors: list[str] = []
    if not keywords:
        return [], errors

    try:
        basic = load_stock_basic(config)
    except TushareError as exc:
        errors.append(f"tushare_init_failed: {exc}")
        return [], errors
    except Exception as exc:
        errors.append(f"tushare_stock_basic_failed: {exc}")
        return [], errors

    results: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()

    # 1) 公司名精确/模糊匹配（新闻摘要中的 A 股公司名）
    for kw in keywords:
        if not any(kw.endswith(s) for s in ("科技", "股份", "电子", "通信", "集团", "光电", "材料")):
            continue
        subset = basic[basic["name"].str.contains(kw[:4], na=False, regex=False)]
        for _, row in subset.head(max_stocks_per_source).iterrows():
            if _append_candidate(
                results,
                seen_tickers,
                ts_code=row["ts_code"],
                name=row["name"],
                rationale=f"Tushare 公司名匹配「{kw}」",
                source_id="tushare-name",
                max_total=max_total,
            ):
                return results, errors

    # 2) 行业字段匹配
    for kw in keywords:
        if len(kw) < 2:
            continue
        subset = basic[basic["industry"].astype(str).str.contains(kw, na=False, regex=False)]
        for _, row in subset.head(max_stocks_per_source).iterrows():
            if _append_candidate(
                results,
                seen_tickers,
                ts_code=row["ts_code"],
                name=row["name"],
                rationale=f"Tushare 行业「{row.get('industry', '')}」匹配关键词「{kw}」",
                source_id="tushare-industry",
                max_total=max_total,
            ):
                return results, errors

    # 3) 概念板块成分股
    try:
        concepts = load_concepts(config)
        pro = get_pro_api(config)
        if not concepts.empty and "name" in concepts.columns:
            matched_concepts: list[tuple[str, str]] = []
            seen_c: set[str] = set()
            for kw in keywords:
                if len(kw) < 2:
                    continue
                hits = concepts[concepts["name"].astype(str).str.contains(kw, na=False, regex=False)]
                for _, row in hits.iterrows():
                    cid = str(row.get("code", ""))
                    cname = str(row.get("name", ""))
                    if cid and cid not in seen_c:
                        seen_c.add(cid)
                        matched_concepts.append((cid, cname))
            for cid, cname in matched_concepts[:max_concepts]:
                try:
                    detail = pro.concept_detail(id=cid)
                except Exception as exc:
                    errors.append(f"tushare_concept_detail_failed:{cname}: {exc}")
                    continue
                if detail is None or detail.empty:
                    continue
                for _, row in detail.head(max_stocks_per_source).iterrows():
                    if _append_candidate(
                        results,
                        seen_tickers,
                        ts_code=str(row.get("ts_code", "")),
                        name=str(row.get("name", "")),
                        rationale=f"Tushare 概念板块「{cname}」成分股",
                        source_id="tushare-concept",
                        max_total=max_total,
                    ):
                        return results, errors
    except Exception as exc:
        errors.append(f"tushare_concept_failed: {exc}")

    if not results:
        errors.append(f"tushare_no_match: keywords={keywords[:10]}")
    return results, errors


def format_lookup_context(candidates: list[dict[str, Any]], keywords: list[str]) -> str:
    if not candidates:
        return f"【Tushare 检索】关键词 {keywords[:10]} 未命中主板成分股。"
    lines = [
        f"【Tushare 检索】关键词：{', '.join(keywords[:10])}",
        "以下为主板成分股候选（供 LLM 交叉验证）：",
    ]
    for c in candidates[:20]:
        lines.append(f"- {c.get('company_name')} ({c.get('ticker')})：{c.get('screening_rationale', '')}")
    return "\n".join(lines)


def lookup_for_state(
    state: dict[str, Any],
    config: dict[str, Any] | Any | None = None,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    keywords = extract_chain_keywords(state)
    candidates, errors = search_main_board_by_keywords(keywords, config=config)
    return candidates, format_lookup_context(candidates, keywords), errors
