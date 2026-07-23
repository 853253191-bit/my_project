# -*- coding: utf-8 -*-
"""向量入库。"""

from __future__ import annotations

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from shike.config import AppConfig, resolve_path
from shike.db.repository import RecipeRepository
from shike.rag.chunk import chunk_recipe
from shike.rag.embeddings import build_embeddings


def ingest_all(config: AppConfig, repo: RecipeRepository | None = None) -> int:
    from shike.config import require_api_key

    require_api_key(config)

    if repo is None:
        db_path = resolve_path(config.data.sqlite_path)
        repo = RecipeRepository(db_path)

    recipes = repo.list_all()
    if not recipes:
        return 0

    docs: list[Document] = []
    for recipe in recipes:
        for ch in chunk_recipe(recipe):
            docs.append(Document(page_content=ch.text, metadata=ch.metadata))

    store_path = resolve_path(config.rag.store_path)
    store_path.mkdir(parents=True, exist_ok=True)

    print(f"开始向量化 {len(docs)} 个 chunk（{len(recipes)} 条食谱）...")
    Chroma.from_documents(
        documents=docs,
        embedding=build_embeddings(config),
        collection_name=config.rag.collection,
        persist_directory=str(store_path),
    )
    print("向量化完成")
    return len(docs)
