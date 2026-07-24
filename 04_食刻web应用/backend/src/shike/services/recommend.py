# -*- coding: utf-8 -*-
"""混合推荐服务：Chroma 硬过滤+向量检索，SQLite 补全详情。"""

from __future__ import annotations

import logging
from typing import Any

from shike.config import AppConfig
from shike.db.repository import RecipeRepository
from shike.rag.vector_store import RecipeVectorStore
from shike.services.title_dedupe import dedupe_recipe_items

logger = logging.getLogger(__name__)


def _ingredient_names(ingredients: Any) -> list[str]:
    """从食材列表提取名称（兼容 str / {name: ...}）。"""
    names: list[str] = []
    if not isinstance(ingredients, list):
        return names
    for item in ingredients:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("ingredient") or "").strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


class HybridRecommender:
    def __init__(self, config: AppConfig, repo: RecipeRepository):
        self.config = config
        self.repo = repo
        self.store = RecipeVectorStore(config)

    def ensure_vector_db(self) -> None:
        """Chroma 未初始化时自动执行迁移。"""
        if self.store.is_ready():
            return
        logger.warning("Chroma 为空，开始自动迁移 ...")
        import os
        import sys
        from pathlib import Path

        from shike.config import resolve_path

        backend_root = Path(__file__).resolve().parents[3]
        if str(backend_root) not in sys.path:
            sys.path.insert(0, str(backend_root))
        from pipeline.migrate_to_vector_db import migrate

        db_path = resolve_path(
            os.getenv("DB_PATH", "") or self.config.data.sqlite_path
        )
        chroma_path = resolve_path(
            os.getenv("CHROMA_PATH", "") or self.config.rag.store_path
        )
        # 必须先关闭已打开的 Chroma 连接，再清空目录，否则会报 readonly/dbmoved
        self.store.close()
        try:
            migrate(db_path=db_path, chroma_path=chroma_path, batch_size=50)
        finally:
            # 迁移后重新打开
            self.store = RecipeVectorStore(self.config)

    def _hit_to_item(self, hit: dict[str, Any]) -> dict[str, Any]:
        rid = str(hit.get("recipe_id") or hit.get("_chroma_id") or "")
        recipe = self.repo.get_by_id(rid) if rid else None
        if recipe:
            return {
                "id": recipe.get("id"),
                "title": recipe.get("title"),
                "decision_summary": recipe.get("decision_summary")
                or (recipe.get("ai_tags") or {}).get("decision_summary", ""),
                "greasiness": recipe.get("greasiness"),
                "spicy_level": recipe.get("spicy_level"),
                "cuisine_main": recipe.get("cuisine_main"),
                "ai_difficulty": recipe.get("ai_difficulty"),
                "estimated_time": recipe.get("estimated_time"),
                "allergens_str": recipe.get("allergens_str"),
                "diet_labels_str": recipe.get("diet_labels_str"),
                "ai_tags": recipe.get("ai_tags"),
                "image_url": recipe.get("image_url"),
                "source_url": recipe.get("source_url"),
                "ingredients": _ingredient_names(recipe.get("ingredients")),
                "distance": hit.get("_distance"),
            }
        return {
            "id": rid,
            "title": hit.get("title"),
            "decision_summary": "",
            "greasiness": hit.get("greasiness"),
            "spicy_level": hit.get("spicy_level"),
            "cuisine_main": hit.get("cuisine_main"),
            "ai_difficulty": hit.get("ai_difficulty"),
            "estimated_time": hit.get("estimated_time"),
            "allergens_str": hit.get("allergens_str"),
            "diet_labels_str": hit.get("diet_labels_str"),
            "ai_tags": None,
            "ingredients": [],
            "distance": hit.get("_distance"),
        }

    def recommend(
        self,
        query_text: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        self.ensure_vector_db()

        # 多取候选，供菜名语义去重后仍能凑满 top_k
        fetch_k = max(top_k * 4, top_k)
        hits = self.store.query(query_text=query_text, filters=filters, top_k=fetch_k)
        if not hits:
            return {
                "count": 0,
                "message": "当前筛选条件下没有找到合适的菜，请放宽条件试试",
                "items": [],
            }

        raw_items = [self._hit_to_item(h) for h in hits]
        items = dedupe_recipe_items(self.config, raw_items, keep=top_k, use_llm=True)
        if not items:
            return {
                "count": 0,
                "message": "当前筛选条件下没有找到合适的菜，请放宽条件试试",
                "items": [],
            }

        return {"count": len(items), "message": "", "items": items}

    def daily_recommendations(self, limit: int = 5) -> dict[str, Any]:
        """每日推荐：随机取样 + 菜名语义去重。"""
        fetch_n = max(limit * 4, limit)
        raw_items: list[dict[str, Any]] = []
        with self.repo._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM recipes ORDER BY RANDOM() LIMIT ?",
                (fetch_n,),
            ).fetchall()
        for row in rows:
            recipe = self.repo._row_to_dict(row)
            raw_items.append({
                "id": recipe.get("id"),
                "title": recipe.get("title"),
                "decision_summary": recipe.get("decision_summary"),
                "cuisine_main": recipe.get("cuisine_main"),
                "estimated_time": recipe.get("estimated_time"),
                "ai_difficulty": recipe.get("ai_difficulty"),
                "image_url": recipe.get("image_url"),
                "ingredients": _ingredient_names(recipe.get("ingredients")),
            })

        items = dedupe_recipe_items(
            self.config, raw_items, keep=limit, use_llm=True
        )
        return {"count": len(items), "items": items}
