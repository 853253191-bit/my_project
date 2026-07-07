# -*- coding: utf-8 -*-
"""Tushare A 股板块检索测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from manus.tools.a_share_lookup import (
    extract_chain_keywords,
    format_lookup_context,
    search_main_board_by_keywords,
)


def test_extract_chain_keywords(filled_pipeline_state_dict):
    kws = extract_chain_keywords(filled_pipeline_state_dict)
    assert "光引擎" in kws or "InP" in str(kws)


@patch("manus.tools.a_share_lookup.get_pro_api")
@patch("manus.tools.a_share_lookup.load_concepts")
@patch("manus.tools.a_share_lookup.load_stock_basic")
def test_search_main_board_by_keywords(mock_basic, mock_concepts, mock_pro):
    mock_basic.return_value = pd.DataFrame(
        [
            {"ts_code": "600584.SH", "name": "长电科技", "industry": "半导体"},
            {"ts_code": "688981.SH", "name": "中芯国际", "industry": "半导体"},
            {"ts_code": "603986.SH", "name": "兆易创新", "industry": "半导体"},
            {"ts_code": "002281.SZ", "name": "光迅科技", "industry": "光通信"},
        ]
    )
    mock_concepts.return_value = pd.DataFrame([{"code": "TS001", "name": "CPO概念"}])
    mock_pro.return_value.concept_detail.return_value = pd.DataFrame(
        [
            {"ts_code": "600487.SH", "name": "亨通光电"},
            {"ts_code": "300308.SZ", "name": "中际旭创"},
        ]
    )
    results, errors = search_main_board_by_keywords(["半导体", "CPO"], config={})
    tickers = {r["ticker"] for r in results}
    assert "600584.SH" in tickers or "603986.SH" in tickers
    assert "688981.SH" not in tickers
    assert "300308.SZ" not in tickers


def test_format_lookup_context_empty():
    text = format_lookup_context([], ["HBM"])
    assert "Tushare" in text
