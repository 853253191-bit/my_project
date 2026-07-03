"""
阶段三：检索重排测试（tests/phase3/test_reranking.py）

主要功能：
- 测试 BgeReranker 空候选、Top-N 截断、metadata 回写 rerank_score
- mock DashScope TextReRank API，校验 model 参数与 index 映射

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase3/test_reranking.py -v
"""
from __future__ import annotations

import pytest

from src.reranking import BgeReranker


@pytest.mark.phase3
class TestBgeReranker:
    def test_rerank_empty_candidates(self):
        reranker = BgeReranker()
        assert reranker.rerank("问题", [], top_n=5) == []

    def test_rerank_maps_metadata_back(self, mocker, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        candidates = [
            {"text": "片段A", "doc_id": "A", "page": 1, "score": 0.5},
            {"text": "片段B", "doc_id": "B", "page": 2, "score": 0.9},
        ]
        mock_call = mocker.patch("src.reranking.dashscope.TextReRank.call")
        mock_call.return_value = {
            "output": {
                "results": [
                    {"index": 1, "relevance_score": 0.95},
                    {"index": 0, "relevance_score": 0.80},
                ]
            }
        }

        reranker = BgeReranker(model="bge-reranker")
        results = reranker.rerank("D06单元控规", candidates, top_n=2)

        assert results[0]["doc_id"] == "B"
        assert results[0]["rerank_score"] == 0.95
        assert results[1]["doc_id"] == "A"
        assert mock_call.call_args.kwargs["model"] == "qwen3-rerank"

    def test_rerank_respects_top_n(self, mocker, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        candidates = [{"text": f"t{i}", "doc_id": str(i), "page": i} for i in range(5)]
        mock_call = mocker.patch("src.reranking.dashscope.TextReRank.call")
        mock_call.return_value = {
            "output": {
                "results": [{"index": i, "relevance_score": 1 - i * 0.1} for i in range(5)]
            }
        }

        reranker = BgeReranker()
        results = reranker.rerank("q", candidates, top_n=2)
        assert len(results) == 2
