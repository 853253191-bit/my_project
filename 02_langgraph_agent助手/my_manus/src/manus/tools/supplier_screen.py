# -*- coding: utf-8 -*-
"""A 股主板过滤（SPEC §4.5.1 / §4.5.2）。"""

from __future__ import annotations

import re
from datetime import date, datetime

from manus.schemas.models import SupplierProfile

_MAIN_PREFIXES = ("600", "601", "603", "605", "000", "001", "002")
_ST_PATTERN = re.compile(r"(^|\W)(\*?ST|S\*ST|SST)(\*?ST)?", re.IGNORECASE)


def parse_ticker_prefix(ticker: str) -> str:
    code = ticker.split(".")[0]
    return code[:3] if len(code) >= 3 else code


def _parse_listing_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def is_eligible_a_share_main(
    ticker: str,
    company_name: str,
    meta: dict | None = None,
    min_listing_days: int = 60,
) -> tuple[bool, str]:
    meta = meta or {}
    prefix = parse_ticker_prefix(ticker)
    exchange = ticker.split(".")[-1].upper() if "." in ticker else ""

    if exchange == "BJ" or prefix.startswith("8") or prefix in ("43", "83", "87", "88", "92"):
        return False, "bse_board"
    if prefix.startswith("688"):
        return False, "star_board"
    if prefix.startswith("300"):
        return False, "chinext_board"

    if not prefix.startswith(_MAIN_PREFIXES):
        return False, "not_main_board_prefix"

    if meta.get("is_st") is True:
        return False, "st_flag"
    if _ST_PATTERN.search(company_name):
        return False, "st_name"

    trade_status = str(meta.get("trade_status", ""))
    if "退市" in trade_status or "delist" in trade_status.lower():
        return False, "delisted"

    listing_raw = meta.get("listing_date")
    if listing_raw:
        listing = _parse_listing_date(str(listing_raw))
        if listing:
            days = (date.today() - listing).days
            if days < min_listing_days:
                return False, f"listing_cooling_{days}d_lt_{min_listing_days}"

    return True, ""


def filter_suppliers(
    candidates: list[SupplierProfile],
    bottleneck_name: str = "",
    min_listing_days: int = 60,
) -> tuple[list[SupplierProfile], list[str], list[dict]]:
    eligible: list[SupplierProfile] = []
    errors: list[str] = []
    excluded: list[dict] = []

    for c in candidates:
        ok, reason = is_eligible_a_share_main(
            c.ticker,
            c.company_name,
            meta={"is_st": c.is_st},
            min_listing_days=min_listing_days,
        )
        if ok:
            eligible.append(c)
        else:
            excluded.append({"ticker": c.ticker, "reason": reason})

    if candidates and not eligible:
        bn = bottleneck_name or (candidates[0].bottleneck_id if candidates else "unknown")
        errors.append(f"no_eligible_a_share_main: {bn}")

    return eligible, errors, excluded
