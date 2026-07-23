# -*- coding: utf-8 -*-
"""DashScope Embedding 封装。"""

from __future__ import annotations

from openai import OpenAI

from shike.config import AppConfig


class DashScopeEmbeddings:
    """实现 LangChain / Chroma 所需的 embed_documents / embed_query 接口。"""

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        clean = [t if isinstance(t, str) and t.strip() else " " for t in texts]
        batch_size = 10
        vectors: list[list[float]] = []
        for i in range(0, len(clean), batch_size):
            batch = clean[i : i + batch_size]
            resp = self._client.embeddings.create(model=self.model, input=batch)
            vectors.extend([item.embedding for item in resp.data])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_embeddings(config: AppConfig) -> DashScopeEmbeddings:
    emb = config.embedding
    api_key = emb.api_key or config.llm.api_key
    return DashScopeEmbeddings(model=emb.model, api_key=api_key, base_url=emb.base_url)
