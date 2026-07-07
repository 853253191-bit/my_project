# -*- coding: utf-8 -*-
"""finance_lookup 测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from manus.tools.finance_lookup import FinanceLookupError, finance_lookup


class TestFinanceLookup:
    def test_success(self):
        mock_data = {
            "revenue": "100亿",
            "gross_margin": "50%",
            "cash_flow": "10亿",
            "debt": "30%",
        }
        with patch("manus.tools.finance_lookup._fetch_from_tushare", return_value=mock_data):
            result = finance_lookup("600519.SH", config={"finance": {"api_key": "x"}})
        assert result.revenue == "100亿"
        assert result.unavailable is False

    def test_raises_on_failure(self):
        with patch("manus.tools.finance_lookup._fetch_from_tushare", side_effect=RuntimeError("timeout")):
            with pytest.raises(FinanceLookupError):
                finance_lookup("600519.SH", config={"finance": {"api_key": "x"}})

    def test_cache(self):
        mock_data = {"revenue": "1", "gross_margin": "2", "cash_flow": "3", "debt": "4"}
        with patch("manus.tools.finance_lookup._fetch_from_tushare", return_value=mock_data) as mock_fetch:
            finance_lookup("600519.SH", cache_ttl_sec=3600, config={"finance": {"api_key": "x"}})
            finance_lookup("600519.SH", cache_ttl_sec=3600, config={"finance": {"api_key": "x"}})
        assert mock_fetch.call_count == 1

    def test_fetch_from_tushare_parses_dataframes(self):
        from manus.tools.finance_lookup import _fetch_from_tushare

        pro = MagicMock()
        pro.income.return_value = pd.DataFrame([{"revenue": 1000}])
        pro.fina_indicator.return_value = pd.DataFrame([{"grossprofit_margin": 22.5, "debt_to_assets": 40.0}])
        pro.cashflow.return_value = pd.DataFrame([{"n_cashflow_act": 500}])
        with patch("manus.tools.finance_lookup.get_pro_api", return_value=pro):
            data = _fetch_from_tushare("600519.SH", config={"finance": {"api_key": "x"}})
        assert data["revenue"] == "1000"
        assert "22.5" in data["gross_margin"]
