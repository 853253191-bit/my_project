# -*- coding: utf-8 -*-
"""案例库分块测试（P4）。"""

from __future__ import annotations

from pathlib import Path

from manus.rag.cases_chunk import chunk_cases_document, format_cases_context


class TestChunkCasesDocument:
    def test_splits_by_post_separator(self):
        path = Path(__file__).parent / "fixtures" / "sample_cases.md"
        chunks = chunk_cases_document(path)
        assert len(chunks) == 2
        assert all(c.metadata["source"] == "aleabitoreddit" for c in chunks)

    def test_post_metadata(self):
        path = Path(__file__).parent / "fixtures" / "sample_cases.md"
        chunks = chunk_cases_document(path)
        first = chunks[0]
        assert first.metadata["post_id"] == "2056761997598028113"
        assert "2026-07-06" in first.metadata["created_at"]
        assert "InP" in first.text

    def test_format_cases_context(self):
        text = format_cases_context(["案例A", "案例B"])
        assert "=== 实战案例库 ===" in text
        assert "案例A" in text
