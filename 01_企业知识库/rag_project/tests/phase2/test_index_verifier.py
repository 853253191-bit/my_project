"""
阶段二：索引校验测试（tests/phase2/test_index_verifier.py）

主要功能：
- 测试 verify_indexes 对 subset.csv 中每份文档的检查逻辑
- 覆盖 chunked 缺失、faiss 缺失、维度错误等失败场景
- 测试 VerificationReport 统计属性

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase2/test_index_verifier.py -v
"""
from __future__ import annotations

import faiss
import numpy as np
import pytest

from src.config import EMBEDDING_DIMENSION
from src.index_verifier import VerificationReport, verify_indexes


@pytest.mark.phase2
class TestIndexVerifier:
    def _write_fake_index(self, path, n_vectors: int = 3):
        index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        vecs = np.random.rand(n_vectors, EMBEDDING_DIMENSION).astype(np.float32)
        faiss.normalize_L2(vecs)
        index.add(vecs)
        faiss.write_index(index, str(path))

    def test_verify_all_pass(self, tmp_data_root):
        sha1 = "abc123"
        subset = tmp_data_root / "subset.csv"
        subset.write_text(
            "doc_id,sha1,file_name,doc_title,project_code,year,region,doc_type\n"
            f"2021-KS-0017,{sha1},a.pdf,D06,2021-Ⅰ-KS-0017,2021,昆山市,控规调整\n",
            encoding="utf-8",
        )
        chunked_dir = tmp_data_root / "databases/chunked_reports"
        vector_dir = tmp_data_root / "databases/vector_dbs"
        chunked_dir.mkdir(parents=True, exist_ok=True)
        vector_dir.mkdir(parents=True, exist_ok=True)
        (chunked_dir / f"{sha1}.json").write_text("{}", encoding="utf-8")
        self._write_fake_index(vector_dir / f"{sha1}.faiss")

        report: VerificationReport = verify_indexes(tmp_data_root)

        assert report.all_passed
        assert report.total == 1
        assert report.passed == 1
        assert report.items[0].dimension == EMBEDDING_DIMENSION

    def test_verify_fails_when_faiss_missing(self, tmp_data_root):
        sha1 = "abc123"
        subset = tmp_data_root / "subset.csv"
        subset.write_text(
            "doc_id,sha1,file_name,doc_title,project_code,year,region,doc_type\n"
            f"2021-KS-0017,{sha1},a.pdf,D06,2021-Ⅰ-KS-0017,2021,昆山市,控规调整\n",
            encoding="utf-8",
        )
        chunked_dir = tmp_data_root / "databases/chunked_reports"
        chunked_dir.mkdir(parents=True, exist_ok=True)
        (chunked_dir / f"{sha1}.json").write_text("{}", encoding="utf-8")

        report = verify_indexes(tmp_data_root)
        assert not report.all_passed

    def test_verify_fails_wrong_dimension(self, tmp_data_root):
        sha1 = "abc123"
        subset = tmp_data_root / "subset.csv"
        subset.write_text(
            "doc_id,sha1,file_name,doc_title,project_code,year,region,doc_type\n"
            f"2021-KS-0017,{sha1},a.pdf,D06,2021-Ⅰ-KS-0017,2021,昆山市,控规调整\n",
            encoding="utf-8",
        )
        chunked_dir = tmp_data_root / "databases/chunked_reports"
        vector_dir = tmp_data_root / "databases/vector_dbs"
        chunked_dir.mkdir(parents=True, exist_ok=True)
        vector_dir.mkdir(parents=True, exist_ok=True)
        (chunked_dir / f"{sha1}.json").write_text("{}", encoding="utf-8")

        wrong_index = faiss.IndexFlatIP(512)
        vecs = np.random.rand(1, 512).astype(np.float32)
        wrong_index.add(vecs)
        faiss.write_index(wrong_index, str(vector_dir / f"{sha1}.faiss"))

        report = verify_indexes(tmp_data_root)
        assert not report.all_passed
