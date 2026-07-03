"""
跨文档向量检索（src/retrieval.py）

主要功能：
- VectorRetriever：遍历所有 {sha1}.faiss，对每个文档索引分别检索 Top-N
- 合并多文档结果，按相似度全局排序取 Top-K
- 返回 chunk 文本及 doc_id、doc_title、page 等元数据

如何调用：
  from pathlib import Path
  from src.retrieval import VectorRetriever

  retriever = VectorRetriever(data_root=Path("data/项目知识库"))
  hits = retriever.retrieve_all("用户问题", per_index_top_n=5, global_top_k=20)
  # 由 QuestionsProcessor / Pipeline 问答流程调用
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from src.faiss_io import read_faiss_index
from src.multimodal_embedding import embed_query as _embed_query


def embed_query(query: str) -> np.ndarray:
    return _embed_query(query)


def merge_retrieval_results(
    result_lists: list[list[dict[str, Any]]],
    global_top_k: int,
) -> list[dict[str, Any]]:
    """合并多索引检索结果，按 score 降序取 global_top_k。"""
    merged: list[dict[str, Any]] = []
    for results in result_lists:
        merged.extend(results)
    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    return merged[:global_top_k]


class VectorRetriever:
    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.chunked_dir = data_root / "databases/chunked_reports"
        self.vector_dir = data_root / "databases/vector_dbs"

    def _load_indexes(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for report_path in self.chunked_dir.glob("*.json"):
            report = json.loads(report_path.read_text(encoding="utf-8"))
            sha1 = report.get("metainfo", {}).get("sha1")
            if not sha1:
                continue
            faiss_path = self.vector_dir / f"{sha1}.faiss"
            if not faiss_path.exists():
                continue
            index = read_faiss_index(faiss_path)
            entries.append({"sha1": sha1, "index": index, "report": report})
        return entries

    def retrieve_all(
        self,
        query: str,
        per_index_top_n: int = 5,
        global_top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """跨所有文档检索并合并结果。"""
        query_vec = embed_query(query)
        all_results: list[list[dict[str, Any]]] = []

        for entry in self._load_indexes():
            index: faiss.Index = entry["index"]
            report = entry["report"]
            metainfo = report["metainfo"]
            chunks = report["content"]["chunks"]
            k = min(per_index_top_n, index.ntotal)
            if k == 0:
                continue
            scores, indices = index.search(query_vec, k)
            hits: list[dict[str, Any]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                chunk = chunks[idx]
                hits.append({
                    "score": float(score),
                    "text": chunk["text"],
                    "page": chunk["page"],
                    "chunk_index": chunk["chunk_index"],
                    "doc_id": metainfo.get("doc_id", ""),
                    "doc_title": metainfo.get("doc_title", ""),
                    "file_name": metainfo.get("file_name", ""),
                    "sha1": metainfo.get("sha1", entry["sha1"]),
                })
            all_results.append(hits)

        return merge_retrieval_results(all_results, global_top_k)
