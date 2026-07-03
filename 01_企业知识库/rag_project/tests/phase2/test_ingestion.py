"""
阶段二：FAISS 建库测试（tests/phase2/test_ingestion.py）

主要功能：
- 测试 VectorDBIngestor 从 chunked JSON 构建 .faiss 索引（mock Embedding）
- 测试 write_index_metadata 元数据字段
- 校验索引维度为 1024

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase2/test_ingestion.py -v
  pytest tests/phase2 -m phase2 -v
"""
from __future__ import annotations

import json

import faiss
import numpy as np
import pytest

from src.config import EMBEDDING_DIMENSION
from src.ingestion import VectorDBIngestor, write_index_metadata


@pytest.mark.phase2
class TestVectorDBIngestor:
    def test_build_index_from_chunked_report(
        self, sample_chunked_report, tmp_data_root, mocker, monkeypatch
    ):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        sha1 = sample_chunked_report["metainfo"]["sha1"]

        chunked_dir = tmp_data_root / "databases/chunked_reports"
        vector_dir = tmp_data_root / "databases/vector_dbs"
        chunked_dir.mkdir(parents=True, exist_ok=True)
        vector_dir.mkdir(parents=True, exist_ok=True)

        report_path = chunked_dir / f"{sha1}.json"
        report_path.write_text(json.dumps(sample_chunked_report, ensure_ascii=False), encoding="utf-8")

        fake_vec = np.random.rand(EMBEDDING_DIMENSION).astype(np.float32)
        mocker.patch(
            "src.ingestion.embed_chunk",
            return_value=fake_vec.tolist(),
        )

        ingestor = VectorDBIngestor(data_root=tmp_data_root)
        meta = ingestor.build_index_for_report(sha1=sha1)

        faiss_path = vector_dir / f"{sha1}.faiss"
        assert faiss_path.exists()
        index = faiss.read_index(str(faiss_path))
        assert index.d == EMBEDDING_DIMENSION
        assert index.ntotal == len(sample_chunked_report["content"]["chunks"])
        assert meta["embedding_model"] == "qwen2.5-vl-embedding"
        assert meta["embedding_dimension"] == 1024

    def test_build_index_calls_embed_per_chunk(
        self, sample_chunked_report, tmp_data_root, mocker, monkeypatch
    ):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        sha1 = sample_chunked_report["metainfo"]["sha1"]
        chunked_dir = tmp_data_root / "databases/chunked_reports"
        chunked_dir.mkdir(parents=True, exist_ok=True)
        (chunked_dir / f"{sha1}.json").write_text(
            json.dumps(sample_chunked_report, ensure_ascii=False), encoding="utf-8"
        )

        mock_embed = mocker.patch(
            "src.ingestion.embed_chunk",
            return_value=[0.0] * EMBEDDING_DIMENSION,
        )
        ingestor = VectorDBIngestor(data_root=tmp_data_root)
        ingestor.build_index_for_report(sha1=sha1)

        assert mock_embed.call_count == len(sample_chunked_report["content"]["chunks"])


@pytest.mark.phase2
class TestIndexMetadata:
    def test_write_index_metadata(self, tmp_path):
        meta_path = tmp_path / "abc.faiss.meta.json"
        meta = write_index_metadata(
            path=meta_path,
            sha1="abc",
            doc_id="2021-KS-0017",
            num_vectors=10,
        )
        assert meta["embedding_model"] == "qwen2.5-vl-embedding"
        assert meta["embedding_dimension"] == 1024
        assert meta_path.exists()
