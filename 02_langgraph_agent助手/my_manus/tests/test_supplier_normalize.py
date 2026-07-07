# -*- coding: utf-8 -*-
"""供应商字段归一化测试。"""

from __future__ import annotations

from manus.tools.supplier_normalize import (
    format_a_share_ticker,
    normalize_supplier_dict,
    parse_supplier_profiles,
)


class TestFormatTicker:
    def test_sh(self):
        assert format_a_share_ticker("600584") == "600584.SH"

    def test_sz(self):
        assert format_a_share_ticker("000001") == "000001.SZ"


class TestNormalizeSupplierDict:
    def test_code_name_alias(self):
        raw = {"code": "600584", "name": "长电科技", "bottleneck_id": "bn-1"}
        norm = normalize_supplier_dict(raw)
        assert norm["ticker"] == "600584.SH"
        assert norm["company_name"] == "长电科技"
        assert norm["business_focus_pct"] == 50.0
        assert norm["coverage_level"] == "medium"
        assert norm["risks"]


class TestParseSupplierProfiles:
    def test_partial_failure(self):
        raw = [
            {"code": "600584", "name": "长电科技", "bottleneck_id": "bn-1"},
            {"code": "688981", "name": "中芯国际", "bottleneck_id": "bn-1"},
            {"foo": "bar"},
        ]
        profiles, errors = parse_supplier_profiles(raw, default_bottleneck_id="bn-1")
        assert len(profiles) == 1
        assert profiles[0].ticker == "600584.SH"
        assert any("688981" in e or "supplier_skip" in e for e in errors)

    def test_real_world_llm_shape(self):
        """复现 run-4ed9775b27c9 中 LLM 返回 code/name 的场景。"""
        raw = [{"code": "600584", "name": "长电科技", "screening_rationale": "先进封装"}]
        profiles, errors = parse_supplier_profiles(raw, default_bottleneck_id="bom-1")
        assert len(profiles) == 1
        assert not errors
        assert profiles[0].company_name == "长电科技"
