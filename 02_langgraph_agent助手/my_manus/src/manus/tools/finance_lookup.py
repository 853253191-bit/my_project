# -*- coding: utf-8 -*-
"""A 股财务查询（Tushare）。"""

from __future__ import annotations

import time
from typing import Any

from manus.schemas.models import Financials
from manus.tools.tushare_client import TushareError, get_pro_api

_cache: dict[str, tuple[float, Financials]] = {}


class FinanceLookupError(Exception):
    pass


def _normalize_ts_code(ticker: str) -> str:
    t = ticker.strip().upper()
    if "." in t:
        return t
    if t.startswith(("600", "601", "603", "605")):
        return f"{t}.SH"
    if t.startswith(("000", "001", "002")):
        return f"{t}.SZ"
    return t


def _fetch_from_tushare(ticker: str, config: dict[str, Any] | Any | None = None) -> dict[str, Any]:
    """从 Tushare 拉取最新财务摘要。"""
    pro = get_pro_api(config)
    ts_code = _normalize_ts_code(ticker)

    revenue = ""
    gross_margin = ""
    cash_flow = ""
    debt = ""

    income = pro.income(ts_code=ts_code, limit=1)
    if income is not None and not income.empty:
        row = income.iloc[0]
        rev = row.get("revenue") or row.get("total_revenue")
        if rev is not None and str(rev) not in ("", "nan"):
            revenue = str(rev)

    indicator = pro.fina_indicator(ts_code=ts_code, limit=1)
    if indicator is not None and not indicator.empty:
        row = indicator.iloc[0]
        gm = row.get("grossprofit_margin")
        if gm is not None and str(gm) not in ("", "nan"):
            gross_margin = f"{gm}%"
        da = row.get("debt_to_assets")
        if da is not None and str(da) not in ("", "nan"):
            debt = f"{da}%"

    cashflow = pro.cashflow(ts_code=ts_code, limit=1)
    if cashflow is not None and not cashflow.empty:
        row = cashflow.iloc[0]
        cf = row.get("n_cashflow_act")
        if cf is not None and str(cf) not in ("", "nan"):
            cash_flow = str(cf)

    if not any([revenue, gross_margin, cash_flow, debt]):
        raise FinanceLookupError(f"无财务数据: {ticker}")

    return {
        "revenue": revenue,
        "gross_margin": gross_margin,
        "cash_flow": cash_flow,
        "debt": debt,
    }


def finance_lookup(
    ticker: str,
    cache_ttl_sec: int = 3600,
    config: dict[str, Any] | Any | None = None,
) -> Financials:
    now = time.time()
    cached = _cache.get(ticker)
    if cached and now - cached[0] < cache_ttl_sec:
        return cached[1]

    try:
        data = _fetch_from_tushare(ticker, config=config)
    except TushareError as exc:
        raise FinanceLookupError(str(exc)) from exc
    except Exception as exc:
        raise FinanceLookupError(str(exc)) from exc

    fin = Financials(
        revenue=data.get("revenue", ""),
        gross_margin=data.get("gross_margin", ""),
        cash_flow=data.get("cash_flow", ""),
        debt=data.get("debt", ""),
        unavailable=False,
    )
    _cache[ticker] = (now, fin)
    return fin


def clear_finance_cache() -> None:
    _cache.clear()
