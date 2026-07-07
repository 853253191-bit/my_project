# -*- coding: utf-8 -*-
"""BOM 回退（Agent3 无瓶颈时输出产业链）测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from manus.pipeline.bom_fallback import bom_to_fallback_bottlenecks, format_bom_chain_text


def test_format_bom_chain_text(filled_pipeline_state_dict):
    text = format_bom_chain_text(filled_pipeline_state_dict["component_node"])
    assert "产业链拆解" in text
    assert "光引擎" in text


def test_bom_to_fallback_bottlenecks(filled_pipeline_state_dict):
    items = bom_to_fallback_bottlenecks(filled_pipeline_state_dict["component_node"], news_id="news-1")
    assert len(items) >= 2
    assert items[0]["component"] == "光引擎"
    assert "BOM 回退" in items[0]["evidence"][1]


class TestAgent3BomFallback:
    @pytest.mark.asyncio
    async def test_empty_bottlenecks_falls_back_to_bom(self, minimal_config_dict, filled_pipeline_state_dict):
        from manus.steps.agent3_bottleneck import run_agent3

        state = {**filled_pipeline_state_dict, "bottlenecks": []}
        with patch("manus.steps.agent3_bottleneck.fetch_agent_rag_context", return_value=("", [])):
            with patch("manus.steps.agent3_bottleneck.invoke_llm_json", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {"bottlenecks": [], "ripple_notes": ""}
                result = await run_agent3(state, config=minimal_config_dict)

        assert result.get("bom_fallback_used") is True
        assert len(result.get("bottlenecks", [])) >= 1
        assert result.get("suggest_deepen_bom") is False
        assert "产业链" in (result.get("ripple_notes") or "")

    @pytest.mark.asyncio
    async def test_no_component_node_still_suggests_deepen(self, minimal_config_dict, filled_pipeline_state_dict):
        from manus.steps.agent3_bottleneck import run_agent3

        state = {k: v for k, v in filled_pipeline_state_dict.items() if k != "component_node"}
        state["bottlenecks"] = []
        with patch("manus.steps.agent3_bottleneck.fetch_agent_rag_context", return_value=("", [])):
            with patch("manus.steps.agent3_bottleneck.invoke_llm_json", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = {"bottlenecks": [], "ripple_notes": ""}
                result = await run_agent3(state, config=minimal_config_dict)

        assert result.get("bom_fallback_used") is not True
        assert result.get("suggest_deepen_bom") is True


class TestAgent4BomFallback:
    @pytest.mark.asyncio
    async def test_returns_a_share_candidates(self, minimal_config_dict, filled_pipeline_state_dict):
        from manus.steps.agent4_quant import _default_checklist_gate, run_agent4

        state = {**filled_pipeline_state_dict, "bom_fallback_used": True, "bottlenecks": []}
        mock_payload = {
            "validations": [],
            "red_team": {
                "alternative_routes": ["a"],
                "falsification_data_needed": ["d1", "d2", "d3"],
                "supply_response_risk": "低",
                "needs_human_review": False,
            },
            "checklist_gate": _default_checklist_gate(),
            "a_share_candidates": [
                {
                    "bottleneck_id": "bom-1",
                    "company_name": "测试股份",
                    "ticker": "600000.SH",
                    "business_focus_pct": 80,
                    "coverage_level": "high",
                    "risks": ["周期波动"],
                    "screening_rationale": "产业链匹配",
                }
            ],
        }
        with patch("manus.steps.agent4_quant.lookup_for_state", return_value=([], "ctx", [])):
            with patch("manus.steps.agent4_quant.invoke_llm_json", new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = mock_payload
                result = await run_agent4(state, config=minimal_config_dict)

        assert len(result.get("a_share_candidates", [])) == 1
        assert "A 股标的" in result.get("step_output_summary", "")
