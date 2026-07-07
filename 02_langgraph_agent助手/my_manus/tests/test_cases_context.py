# -*- coding: utf-8 -*-
"""案例库 RAG 上下文测试（P4）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from manus.rag.context import (
    CASES_QUERY_TEMPLATES,
    bottleneck_hint_from_state,
    fetch_cases_context,
)


class TestCasesQueryTemplates:
    def test_agent3_and_agent5(self):
        assert "agent3" in CASES_QUERY_TEMPLATES
        assert "agent5" in CASES_QUERY_TEMPLATES
        assert "{bottleneck_name}" in CASES_QUERY_TEMPLATES["agent3"]


class TestBottleneckHint:
    def test_from_bottlenecks(self, filled_pipeline_state_dict):
        hint = bottleneck_hint_from_state(filled_pipeline_state_dict)
        assert hint == "InP 基板"

    def test_from_component_node(self, filled_pipeline_state_dict):
        state = {**filled_pipeline_state_dict, "bottlenecks": []}
        hint = bottleneck_hint_from_state(state)
        assert hint == "光引擎"


class TestFetchCasesContext:
    def test_store_missing(self, minimal_config_dict):
        with patch("manus.rag.context.get_store", return_value=None):
            text, errors = fetch_cases_context("InP 基板", "agent3", minimal_config_dict)
        assert text == ""
        assert any("CASES_EMPTY" in e for e in errors)

    def test_retrieve_cases(self, minimal_config_dict):
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [
            (MagicMock(page_content="CPO 案例正文", metadata={}), 0.88),
        ]
        with patch("manus.rag.context.get_store", return_value=mock_store):
            text, errors = fetch_cases_context("InP 基板", "agent3", minimal_config_dict)
        assert "=== 实战案例库 ===" in text
        assert "CPO" in text
        assert errors == []
