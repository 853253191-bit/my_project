# -*- coding: utf-8 -*-
"""混合检索编排。"""

from __future__ import annotations

from typing import Any

from langchain_chroma import Chroma

from shike.config import AppConfig, resolve_path
from shike.db.repository import RecipeRepository
from shike.rag.chunk import chunk_recipe
from shike.rag.embeddings import build_embeddings
from shike.rag.reranker import RecipeReranker


COOK_TIME_MAP = {
    "15分钟内": 15,
    "30分钟内": 30,
    "1小时内": 60,
    "不限": None,
}


def build_query(form: dict[str, Any], extra: str = "") -> str:
    parts = [
        f"心情{form.get('mood', '')}",
        f"口味{','.join(form.get('taste', []))}",
        f"{form.get('servings', 2)}人份",
        f"健康目标{form.get('health_goal', '')}",
        f"食材{','.join(form.get('ingredients', []))}",
        form.get("free_text", ""),
        extra,
    ]
    return " ".join(p for p in parts if p.strip())


class RecipeRetriever:
    def __init__(self, config: AppConfig, repo: RecipeRepository):
        self.config = config
        self.repo = repo
        self.reranker = RecipeReranker(config)
        store_path = resolve_path(config.rag.store_path)
        self._vectorstore = Chroma(
            collection_name=config.rag.collection,
            embedding_function=build_embeddings(config),
            persist_directory=str(store_path),
        )

    def retrieve(
        self,
        query: str,
        form: dict[str, Any] | None = None,
        top_k: int | None = None,
        rerank_top_n: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        k = top_k or self.config.rag.top_k
        n = rerank_top_n or self.config.rag.rerank_top_n

        docs = self._vectorstore.similarity_search_with_score(query, k=k)
        candidates: list[dict[str, Any]] = []
        for doc, score in docs:
            candidates.append({
                "text": doc.page_content,
                "score": float(score),
                "recipe_id": doc.metadata.get("recipe_id", ""),
                "type": doc.metadata.get("type", ""),
                "title": doc.metadata.get("title", ""),
            })

        if form:
            max_minutes = COOK_TIME_MAP.get(form.get("cook_time", ""))
            tag_filtered = self.repo.filter_by_tags(
                mood=form.get("mood"),
                taste=form.get("taste"),
                health_goal=form.get("health_goal"),
                max_cook_minutes=max_minutes,
                spice_level=form.get("spice_level"),
                limit=10,
            )
            existing_ids = {c["recipe_id"] for c in candidates}
            for recipe in tag_filtered:
                if recipe["id"] not in existing_ids:
                    chunks = chunk_recipe(recipe)
                    if chunks:
                        candidates.append({
                            "text": chunks[0].text,
                            "score": 0.5,
                            "recipe_id": recipe["id"],
                            "type": "overview",
                            "title": recipe.get("title", ""),
                        })

        reranked = self.reranker.rerank(query, candidates, top_n=n)

        recipe_ids: list[str] = []
        seen: set[str] = set()
        for c in reranked:
            rid = c.get("recipe_id", "")
            if rid and rid not in seen:
                seen.add(rid)
                recipe_ids.append(rid)

        full_context: list[dict[str, Any]] = []
        for rid in recipe_ids:
            recipe = self.repo.get_by_id(rid)
            if recipe:
                for ch in chunk_recipe(recipe):
                    full_context.append({"text": ch.text, "recipe_id": rid, "title": recipe.get("title", "")})

        if not full_context:
            full_context = reranked

        max_chars = self.config.rag.max_context_chars
        trimmed: list[dict[str, Any]] = []
        total = 0
        for item in full_context:
            if total + len(item["text"]) > max_chars:
                break
            trimmed.append(item)
            total += len(item["text"])

        return trimmed[:n * 2], recipe_ids
