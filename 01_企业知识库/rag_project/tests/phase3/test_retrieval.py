"""
阶段三：跨文档检索测试（tests/phase3/test_retrieval.py）

主要功能：
- 测试 merge_retrieval_results 多索引结果合并与 Top-K 截断
- 测试 VectorRetriever.retrieve_all 跨文档检索（mock embed_query）
- 校验检索结果包含 score、text、page、doc_id 等必需字段

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase3/test_retrieval.py -v
  pytest tests/phase3 -m phase3 -v
"""
from __future__ import annotations

import json

import faiss
import numpy as np
import pytest

from src.config import EMBEDDING_DIMENSION
from src.retrieval import VectorRetriever, merge_retrieval_results


@pytest.mark.phase3
class TestMergeRetrievalResults:
    def test_merge_sorts_by_score_desc(self):
        a = [{"score": 0.5, "doc_id": "A", "text": "a"}]
        b = [{"score": 0.9, "doc_id": "B", "text": "b"}]
        merged = merge_retrieval_results([a, b], global_top_k=2)
        assert merged[0]["doc_id"] == "B"
        assert merged[1]["doc_id"] == "A"

    def test_merge_respects_global_top_k(self):
        items = [{"score": i * 0.1, "doc_id": str(i)} for i in range(10)]
        merged = merge_retrieval_results([items], global_top_k=3)
        assert len(merged) == 3


@pytest.mark.phase3
class TestRetrieveAll:
    def _setup_index(self, tmp_data_root, sha1, doc_id, doc_title, chunks):
        chunked_dir = tmp_data_root / "databases/chunked_reports"
        vector_dir = tmp_data_root / "databases/vector_dbs"
        chunked_dir.mkdir(parents=True, exist_ok=True)
        vector_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "metainfo": {
                "sha1": sha1,
                "doc_id": doc_id,
                "doc_title": doc_title,
                "file_name": f"{doc_id}.pdf",
            },
            "content": {"chunks": chunks},
        }
        (chunked_dir / f"{sha1}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8"
        )

        index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        vecs = np.random.rand(len(chunks), EMBEDDING_DIMENSION).astype(np.float32)
        faiss.normalize_L2(vecs)
        index.add(vecs)
        faiss.write_index(index, str(vector_dir / f"{sha1}.faiss"))

    def test_retrieve_all_merges_multiple_indexes(self, tmp_data_root, mocker):
        query_vec = np.random.rand(1, EMBEDDING_DIMENSION).astype(np.float32)
        faiss.normalize_L2(query_vec)
        mocker.patch("src.retrieval.embed_query", return_value=query_vec)

        self._setup_index(
            tmp_data_root, "sha1_a", "2021-KS-0017", "D06单元控规调整",
            [{"chunk_index": 0, "page": 1, "text": "用地性质", "image_paths": []}],
        )
        self._setup_index(
            tmp_data_root, "sha1_b", "2021-KS-0027", "东部新城核心区",
            [{"chunk_index": 0, "page": 2, "text": "空间结构", "image_paths": []}],
        )

        retriever = VectorRetriever(data_root=tmp_data_root)
        results = retriever.retrieve_all("东部新城空间结构", per_index_top_n=1, global_top_k=2)

        assert len(results) <= 2
        doc_ids = {r["doc_id"] for r in results}
        assert doc_ids.issubset({"2021-KS-0017", "2021-KS-0027"})

    def test_retrieve_all_result_fields(self, tmp_data_root, mocker):
        query_vec = np.random.rand(1, EMBEDDING_DIMENSION).astype(np.float32)
        faiss.normalize_L2(query_vec)
        mocker.patch("src.retrieval.embed_query", return_value=query_vec)

        self._setup_index(
            tmp_data_root, "sha1_a", "2021-KS-0017", "D06单元控规调整",
            [{"chunk_index": 0, "page": 5, "text": "二类居住用地", "image_paths": []}],
        )

        retriever = VectorRetriever(data_root=tmp_data_root)
        results = retriever.retrieve_all("D06控规", global_top_k=1)

        assert len(results) == 1
        required = {"score", "text", "page", "chunk_index", "doc_id", "doc_title", "file_name", "sha1"}
        assert required.issubset(results[0].keys())
