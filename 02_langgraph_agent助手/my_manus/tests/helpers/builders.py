# -*- coding: utf-8 -*-
"""测试数据构造器，对齐 SPEC 附录 A。"""

from __future__ import annotations

from typing import Any


def make_supplier(
    *,
    ticker: str = "600519.SH",
    company_name: str = "贵州茅台",
    bottleneck_id: str = "bn-1",
    is_st: bool = False,
    listing_board: str = "main",
    market: str = "CN",
    **extra: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "bottleneck_id": bottleneck_id,
        "company_name": company_name,
        "ticker": ticker,
        "market": market,
        "listing_board": listing_board,
        "is_st": is_st,
        "business_focus_pct": 90.0,
        "coverage_level": "medium",
        "risks": ["估值风险"],
        "catalysts": ["产能释放"],
    }
    base.update(extra)
    return base


def make_checklist_gate(*, result: str = "pass", hard_fail: bool = False) -> dict[str, Any]:
    hard_items = [
        {"id": "H1_terminal_demand", "passed": True},
        {"id": "H2_bom_depth", "passed": True},
        {"id": "H3_supply_test", "passed": not hard_fail},
        {"id": "H4_quantitative", "passed": True},
    ]
    failed = [h["id"] for h in hard_items if not h["passed"]]
    return {
        "result": result if not hard_fail else "hard_fail",
        "hard_items": hard_items,
        "soft_items": [],
        "failed_hard_ids": failed,
        "auto_retry_attempted": False,
    }
