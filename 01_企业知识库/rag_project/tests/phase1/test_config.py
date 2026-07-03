"""
阶段一：全局配置测试（tests/phase1/test_config.py）

主要功能：
- 校验 EMBEDDING_MODEL、EMBEDDING_DIMENSION、RERANK_MODEL 等常量符合 SPEC
- 校验 EnterpriseRunConfig 默认值（重排开关、Top-K、问答模型等）
- 校验 SUBSET_CSV_COLUMNS 列顺序

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase1/test_config.py -v
  pytest tests/phase1 -m phase1 -v
"""
from __future__ import annotations

import pytest

from src.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    NOT_FOUND_ANSWER,
    RERANK_MODEL,
    SUBSET_CSV_COLUMNS,
    enterprise_config,
)


@pytest.mark.phase1
class TestEmbeddingConstants:
    def test_embedding_model_is_qwen25_vl(self):
        assert EMBEDDING_MODEL == "qwen2.5-vl-embedding"

    def test_embedding_dimension_is_1024(self):
        assert EMBEDDING_DIMENSION == 1024

    def test_rerank_model_is_qwen3_rerank(self):
        assert RERANK_MODEL == "qwen3-rerank"


@pytest.mark.phase1
class TestSubsetCsvSchema:
    def test_subset_csv_columns(self):
        assert SUBSET_CSV_COLUMNS == [
            "doc_id",
            "sha1",
            "file_name",
            "doc_title",
            "project_code",
            "year",
            "region",
            "doc_type",
        ]


@pytest.mark.phase1
class TestEnterpriseConfig:
    def test_enterprise_config_defaults(self):
        cfg = enterprise_config()
        assert cfg.embedding_model == "qwen2.5-vl-embedding"
        assert cfg.embedding_dimension == 1024
        assert cfg.use_reranking is True
        assert cfg.rerank_model == "qwen3-rerank"
        assert cfg.rerank_sample_size == 20
        assert cfg.top_n_retrieval == 10
        assert cfg.use_serialized_tables is False
        assert cfg.parent_document_retrieval is True
        assert cfg.api_provider == "dashscope"
        assert cfg.answering_model == "qwen-plus"


@pytest.mark.phase3
class TestNotFoundMessage:
    def test_not_found_answer_text(self):
        assert NOT_FOUND_ANSWER == "知识库中未找到相关信息"
