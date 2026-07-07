# -*- coding: utf-8 -*-
"""RAG 检索测试（SPEC §5.3 / §5.4 / §5.5）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from manus.rag.retriever import (
    AGENT_QUERY_TEMPLATES,
    StrategyRetriever,
    build_fallback_context,
)


class TestAgentQueryTemplates:
    def test_all_six_agents_have_template(self):
        for agent in ["agent1", "agent2", "agent3", "agent4", "agent5", "agent6"]:
            assert agent in AGENT_QUERY_TEMPLATES
            assert len(AGENT_QUERY_TEMPLATES[agent]) > 0


class TestStrategyRetriever:
    def test_retrieve_top_k(self, minimal_config_dict):
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [
            (MagicMock(page_content="终端需求门槛", metadata={"title": "三、终端需求"}), 0.9),
            (MagicMock(page_content="产业链拆解", metadata={"title": "四、拆解"}), 0.85),
        ]
        retriever = StrategyRetriever(store=mock_store, config=minimal_config_dict["rag"])
        chunks, scores = retriever.retrieve("agent2", query_extra="CPO")
        assert len(chunks) == 2
        assert scores[0] >= scores[1]

    def test_score_threshold_filters(self, minimal_config_dict):
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [
            (MagicMock(page_content="低分", metadata={}), 0.2),
        ]
        retriever = StrategyRetriever(store=mock_store, config=minimal_config_dict["rag"])
        chunks, _ = retriever.retrieve("agent2")
        assert chunks == []

    def test_empty_store_uses_fallback(self, minimal_config_dict):
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = []
        retriever = StrategyRetriever(store=mock_store, config=minimal_config_dict["rag"])
        chunks, errors = retriever.retrieve_with_fallback("agent2")
        assert len(chunks) >= 1
        assert any("RAG_EMPTY" in e or "fallback" in e.lower() for e in errors)


class TestBuildFallbackContext:
    def test_contains_seven_step_flow(self):
        ctx = build_fallback_context()
        assert "终端需求" in ctx or "七步" in ctx
