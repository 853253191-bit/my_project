# -*- coding: utf-8 -*-
"""检索结果重排。"""

from __future__ import annotations

import logging
from typing import Any

import dashscope

from shike.config import AppConfig, require_api_key

logger = logging.getLogger(__name__)


class RecipeReranker:
    def __init__(self, config: AppConfig):
        self.model = config.rerank.model
        self.enabled = config.rerank.enabled
        self.api_key = require_api_key(config)
        dashscope.api_key = self.api_key

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        if not self.enabled:
            return candidates[:top_n]

        documents = [c["text"] for c in candidates]
        response = dashscope.TextReRank.call(
            model=self.model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(candidates)),
        )
        output = response.get("output") if isinstance(response, dict) else getattr(response, "output", None)
        if not output or not output.get("results"):
            logger.warning("重排 API 失败，降级为向量分数排序")
            return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:top_n]

        reranked: list[dict[str, Any]] = []
        for item in output["results"]:
            idx = item["index"]
            merged = dict(candidates[idx])
            merged["rerank_score"] = item["relevance_score"]
            reranked.append(merged)
        return reranked[:top_n]
