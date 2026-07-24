# -*- coding: utf-8 -*-
"""Chroma 向量库封装：硬过滤 metadata + 语义检索 document。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from openai import OpenAI

from shike.config import AppConfig, resolve_path, resolve_llm_api_key

logger = logging.getLogger(__name__)

COLLECTION_NAME = "recipes"


class RecipeVectorStore:
    """混合检索底层：document 做向量相似度，metadata 做硬过滤。"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.chroma_path = resolve_path(
            os.getenv("CHROMA_PATH", "") or config.rag.store_path
        )
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.chroma_path))
        self._collection = None
        self._embed_client: OpenAI | None = None
        self._embed_model = ""

    def close(self) -> None:
        """释放 Chroma 连接，便于迁移时安全清空目录。"""
        self._collection = None
        self._client = None
        self._embed_client = None
        self._embed_model = ""

    def _ensure_client(self):
        if self._client is None:
            self.chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.chroma_path))
        return self._client

    def _ensure_embed_client(self) -> tuple[OpenAI, str]:
        if self._embed_client is not None:
            return self._embed_client, self._embed_model
        emb = self.config.embedding
        api_key = resolve_llm_api_key(self.config)
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or emb.base_url
        model = (
            os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
            or emb.model
            or "text-embedding-v3"
        )
        if not api_key or not base_url:
            raise RuntimeError("Embedding API 未配置（OPENAI_API_KEY / BASE_URL）")
        self._embed_client = OpenAI(api_key=api_key, base_url=base_url)
        self._embed_model = model
        return self._embed_client, self._embed_model

    def is_ready(self) -> bool:
        try:
            col = self.get_collection()
            return col.count() > 0
        except Exception:  # noqa: BLE001
            return False

    def get_collection(self):
        if self._collection is None:
            client = self._ensure_client()
            # 与 migrate 一致：提高 sync_threshold，规避 Windows HNSW 持久化损坏
            self._collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:batch_size": 20000,
                    "hnsw:sync_threshold": 20000,
                },
            )
        return self._collection

    def count(self) -> int:
        return int(self.get_collection().count())

    def embed_query(self, text: str) -> list[float]:
        client, model = self._ensure_embed_client()
        resp = client.embeddings.create(model=model, input=[text or " "])
        return resp.data[0].embedding

    def build_where_filter(self, filters: dict[str, Any] | None) -> dict[str, Any] | None:
        """构造 Chroma where 硬过滤条件。

        说明：
        - greasiness / spicy_level / estimated_time：数值比较（$lte）
        - cuisine_main / ai_difficulty：精确匹配
        - 过敏原 / 饮食标签：Chroma metadata 不稳妥支持 $regex，在上层做二次过滤
        """
        if not filters:
            return None

        def _real_str(val: Any) -> str | None:
            """忽略空串与 Swagger 占位 string。"""
            if val is None:
                return None
            s = str(val).strip()
            if not s or s.lower() in {"string", "null", "none"}:
                return None
            return s

        clauses: list[dict[str, Any]] = []

        if filters.get("greasiness_max") is not None:
            clauses.append({"greasiness": {"$lte": int(filters["greasiness_max"])}})
            # 同时排除缺省占位 -1
            clauses.append({"greasiness": {"$gte": 0}})

        if filters.get("spicy_level_max") is not None:
            clauses.append({"spicy_level": {"$lte": int(filters["spicy_level_max"])}})
            clauses.append({"spicy_level": {"$gte": 0}})

        cuisine = _real_str(filters.get("cuisine_main"))
        if cuisine:
            clauses.append({"cuisine_main": {"$eq": cuisine}})

        difficulty = _real_str(filters.get("ai_difficulty"))
        if difficulty:
            clauses.append({"ai_difficulty": {"$eq": difficulty}})

        if filters.get("estimated_time_max") is not None:
            clauses.append(
                {"estimated_time": {"$lte": int(filters["estimated_time_max"])}}
            )
            clauses.append({"estimated_time": {"$gte": 0}})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _pass_soft_filters(meta: dict[str, Any], filters: dict[str, Any] | None) -> bool:
        """过敏原 / 饮食标签二次过滤（字符串包含判断）。"""
        if not filters:
            return True
        allergens = str(meta.get("allergens_str") or "")
        diets = str(meta.get("diet_labels_str") or "")

        for a in filters.get("exclude_allergens") or []:
            a = str(a).strip()
            if a and a in allergens:
                return False

        for d in filters.get("include_diet_labels") or []:
            d = str(d).strip()
            if d and d not in diets:
                return False
        return True

    def query(
        self,
        query_text: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """硬过滤 + 向量语义检索，返回 metadata 列表（按相似度排序）。"""
        collection = self.get_collection()
        if collection.count() == 0:
            return []

        where = self.build_where_filter(filters)
        # 多取一些，供过敏原/饮食标签二次过滤
        fetch_n = max(top_k * 5, top_k)

        kwargs: dict[str, Any] = {
            "query_embeddings": [self.embed_query(query_text)],
            "n_results": min(fetch_n, max(collection.count(), 1)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        try:
            results = collection.query(**kwargs)
        except Exception as exc:  # noqa: BLE001
            # where 过严或语法不兼容时，退化为无硬过滤检索 + 本地过滤
            logger.warning("Chroma where 查询失败，回退无 where: %s", exc)
            kwargs.pop("where", None)
            results = collection.query(**kwargs)

        metadatas = (results.get("metadatas") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        ids = (results.get("ids") or [[]])[0]

        out: list[dict[str, Any]] = []
        for i, meta in enumerate(metadatas):
            meta = dict(meta or {})
            if not self._pass_soft_filters(meta, filters):
                continue
            meta["_document"] = documents[i] if i < len(documents) else ""
            meta["_distance"] = distances[i] if i < len(distances) else None
            meta["_chroma_id"] = ids[i] if i < len(ids) else meta.get("recipe_id")
            out.append(meta)
            if len(out) >= top_k:
                break
        return out

    def sample(self, limit: int = 5) -> list[dict[str, Any]]:
        """随机/顺序取样（daily_recommendations 用）。"""
        collection = self.get_collection()
        total = collection.count()
        if total <= 0:
            return []
        # peek 取前 limit 条；真正随机可在上层打乱
        data = collection.peek(limit=min(limit * 3, total))
        metas = data.get("metadatas") or []
        docs = data.get("documents") or []
        ids = data.get("ids") or []
        items: list[dict[str, Any]] = []
        for i, meta in enumerate(metas):
            m = dict(meta or {})
            m["_document"] = docs[i] if i < len(docs) else ""
            m["_chroma_id"] = ids[i] if i < len(ids) else m.get("recipe_id")
            items.append(m)
        import random

        random.shuffle(items)
        return items[:limit]
