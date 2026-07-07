# -*- coding: utf-8 -*-
"""Agent5 供应商筛选测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestAgent5Supplier:
    @pytest.mark.asyncio
    async def test_llm_code_name_normalized(self, minimal_config_dict, filled_pipeline_state_dict):
        from manus.steps.agent5_supplier import run_agent5

        state = {**filled_pipeline_state_dict}
        tushare_hit = [
            {
                "ticker": "603986.SH",
                "company_name": "兆易创新",
                "bottleneck_id": "bn-1",
                "business_focus_pct": 60,
                "coverage_level": "medium",
                "risks": ["周期"],
                "screening_rationale": "tushare",
            }
        ]
        with patch("manus.steps.agent5_supplier.lookup_for_state", return_value=(tushare_hit, "ctx", [])):
            with patch("manus.steps.agent5_supplier.fetch_agent_rag_context", return_value=("", [])):
                with patch("manus.steps.agent5_supplier.invoke_llm_json", new_callable=AsyncMock) as mock_llm:
                    mock_llm.return_value = {
                        "suppliers": [
                            {"code": "600584", "name": "长电科技", "screening_rationale": "封装"},
                        ]
                    }
                    with patch("manus.steps.agent5_supplier.finance_lookup") as mock_fin:
                        from manus.schemas.models import Financials

                        mock_fin.return_value = Financials(revenue="100亿")
                        result = await run_agent5(state, config=minimal_config_dict)

        tickers = {s["ticker"] for s in result.get("suppliers", [])}
        assert "600584.SH" in tickers
        assert "603986.SH" in tickers
        assert not any("agent_error" in e for e in result.get("errors", []))
