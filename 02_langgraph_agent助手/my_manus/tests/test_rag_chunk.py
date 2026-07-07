# -*- coding: utf-8 -*-
"""RAG 分块测试（SPEC §5.2）。"""

from __future__ import annotations

from manus.rag.chunk import chunk_strategy_document, format_rag_context


class TestChunkStrategyDocument:
    def test_splits_by_headings(self, strategy_txt_path):
        chunks = chunk_strategy_document(strategy_txt_path)
        assert len(chunks) >= 5
        section_ids = {c.metadata["section_id"] for c in chunks}
        assert any("一" in sid or "1" in sid for sid in section_ids)

    def test_chunk_metadata(self, strategy_txt_path):
        chunks = chunk_strategy_document(strategy_txt_path)
        first = chunks[0]
        assert "section_id" in first.metadata
        assert "title" in first.metadata
        assert len(first.text.strip()) > 0

    def test_contains_terminal_demand_section(self, strategy_txt_path):
        chunks = chunk_strategy_document(strategy_txt_path)
        titles = " ".join(c.metadata.get("title", "") for c in chunks)
        assert "终端需求" in titles or "第一步" in titles


class TestFormatRagContext:
    def test_wrapper_format(self):
        text = format_rag_context(["chunk-a", "chunk-b"])
        assert "=== 策略知识库 ===" in text
        assert "chunk-a" in text
        assert "chunk-b" in text

    def test_respects_max_chars(self):
        long_chunks = ["x" * 5000, "y" * 5000]
        text = format_rag_context(long_chunks, max_context_chars=6000)
        assert len(text) <= 6000 + len("=== 策略知识库 ===\n")
