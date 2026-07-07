# -*- coding: utf-8 -*-
"""A 股主板过滤测试（SPEC §4.5.1 / §4.5.2）。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from manus.schemas.models import SupplierProfile
from manus.tools.supplier_screen import (
    filter_suppliers,
    is_eligible_a_share_main,
    parse_ticker_prefix,
)
from tests.helpers.builders import make_supplier


class TestParseTickerPrefix:
    @pytest.mark.parametrize(
        "ticker,prefix",
        [
            ("600519.SH", "600"),
            ("000001.SZ", "000"),
            ("002415.SZ", "002"),
            ("688981.SH", "688"),
            ("300750.SZ", "300"),
            ("830799.BJ", "830"),
        ],
    )
    def test_prefix_extraction(self, ticker: str, prefix: str):
        assert parse_ticker_prefix(ticker) == prefix


class TestIsEligibleAShareMain:
    @pytest.mark.parametrize(
        "ticker",
        ["600519.SH", "601318.SH", "603986.SH", "605117.SH", "000001.SZ", "001979.SZ", "002415.SZ"],
    )
    def test_main_board_passes(self, ticker: str):
        ok, reason = is_eligible_a_share_main(ticker, "测试公司", meta={"is_st": False})
        assert ok is True
        assert reason == ""

    @pytest.mark.parametrize(
        "ticker,expected_reason",
        [
            ("688981.SH", "star"),
            ("300750.SZ", "chinext"),
            ("830799.BJ", "bse"),
            ("872925.BJ", "bse"),
        ],
    )
    def test_excluded_boards(self, ticker: str, expected_reason: str):
        ok, reason = is_eligible_a_share_main(ticker, "测试公司", meta={"is_st": False})
        assert ok is False
        assert expected_reason in reason

    def test_st_by_name(self):
        ok, reason = is_eligible_a_share_main("600519.SH", "*ST测试", meta={"is_st": False})
        assert ok is False
        assert "st" in reason.lower()

    def test_st_by_meta_flag(self):
        ok, reason = is_eligible_a_share_main("600519.SH", "正常公司", meta={"is_st": True})
        assert ok is False

    def test_delisted_status(self):
        ok, reason = is_eligible_a_share_main(
            "600519.SH", "正常公司", meta={"is_st": False, "trade_status": "退市"}
        )
        assert ok is False
        assert "退市" in reason or "delist" in reason.lower()

    def test_new_listing_cooling(self):
        recent = (date.today() - timedelta(days=30)).isoformat()
        ok, reason = is_eligible_a_share_main(
            "603000.SH",
            "新股公司",
            meta={"is_st": False, "listing_date": recent},
            min_listing_days=60,
        )
        assert ok is False
        assert "listing" in reason.lower() or "上市" in reason


class TestFilterSuppliers:
    def test_filter_mixed_candidates(self):
        candidates = [
            SupplierProfile.model_validate(make_supplier(ticker="600519.SH")),
            SupplierProfile.model_validate(make_supplier(ticker="688981.SH", company_name="科创板样例")),
            SupplierProfile.model_validate(make_supplier(ticker="300750.SZ", company_name="创业板样例")),
        ]
        eligible, errors, excluded = filter_suppliers(candidates)
        assert len(eligible) == 1
        assert eligible[0].ticker == "600519.SH"
        assert len(excluded) == 2
        assert any("688" in e.get("ticker", "") for e in excluded)

    def test_no_eligible_emits_error(self):
        candidates = [
            SupplierProfile.model_validate(make_supplier(ticker="688981.SH", company_name="科创板")),
        ]
        eligible, errors, excluded = filter_suppliers(candidates, bottleneck_name="InP基板")
        assert eligible == []
        assert any("no_eligible_a_share_main" in e for e in errors)
