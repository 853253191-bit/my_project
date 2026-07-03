"""
全局配置与运行参数（src/config.py）

主要功能：
- 定义 Embedding/Rerank/LLM 模型名、向量维度、subset.csv 列名等常量
- 提供 EnterpriseRunConfig 数据类，控制检索 Top-K、是否重排、问答模型等

如何调用：
  from src.config import enterprise_config, EMBEDDING_MODEL, NOT_FOUND_ANSWER
  cfg = enterprise_config()
  # cfg.use_reranking / cfg.top_n_retrieval / cfg.answering_model 等
"""
from __future__ import annotations

from dataclasses import dataclass

EMBEDDING_MODEL = "qwen2.5-vl-embedding"
EMBEDDING_DIMENSION = 1024
RERANK_MODEL = "qwen3-rerank"
NOT_FOUND_ANSWER = "知识库中未找到相关信息"
PER_INDEX_TOP_N = 5

SUBSET_CSV_COLUMNS = [
    "doc_id",
    "sha1",
    "file_name",
    "doc_title",
    "project_code",
    "year",
    "region",
    "doc_type",
]


@dataclass
class EnterpriseRunConfig:
    embedding_model: str = EMBEDDING_MODEL
    embedding_dimension: int = EMBEDDING_DIMENSION
    use_reranking: bool = True
    rerank_model: str = RERANK_MODEL
    rerank_sample_size: int = 20
    top_n_retrieval: int = 10
    per_index_top_n: int = PER_INDEX_TOP_N
    use_serialized_tables: bool = False
    parent_document_retrieval: bool = True
    api_provider: str = "dashscope"
    answering_model: str = "qwen-plus"
    config_suffix: str = "_enterprise"


def enterprise_config() -> EnterpriseRunConfig:
    return EnterpriseRunConfig()
