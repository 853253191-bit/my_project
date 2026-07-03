"""
检索结果重排（src/reranking.py）

主要功能：
- 调用 DashScope TextReRank（qwen3-rerank）对向量检索候选重新排序
- API 失败时自动降级为按向量 score 排序

如何调用：
  from src.reranking import BgeReranker

  reranker = BgeReranker(model="qwen3-rerank")
  ranked = reranker.rerank("用户问题", candidates, top_n=10)
  # 由 QuestionsProcessor._rerank_if_enabled() 在 use_reranking=True 时调用
"""
from __future__ import annotations

import os
from typing import Any

import dashscope

from src.config import RERANK_MODEL
from src.multimodal_embedding import require_dashscope_api_key


class BgeReranker:
    def __init__(self, model: str = RERANK_MODEL):
        self.model = model

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        require_dashscope_api_key()
        documents = [c["text"] for c in candidates]
        response = dashscope.TextReRank.call(
            model=self.model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(candidates)),
        )
        output = response.get("output") if isinstance(response, dict) else getattr(response, "output", None)
        if not output or not output.get("results"):
            code = response.get("code") if isinstance(response, dict) else getattr(response, "code", "")
            message = response.get("message") if isinstance(response, dict) else getattr(response, "message", "")
            # API 失败时降级为向量检索分数排序
            fallback = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
            if code or message:
                import logging
                logging.warning(f"重排 API 失败 ({code}): {message}，已降级为向量排序")
            return fallback[:top_n]

        results = output["results"]
        reranked: list[dict[str, Any]] = []
        for item in results:
            idx = item["index"]
            merged = dict(candidates[idx])
            merged["rerank_score"] = item["relevance_score"]
            reranked.append(merged)
        return reranked[:top_n]
