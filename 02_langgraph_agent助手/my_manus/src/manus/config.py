# -*- coding: utf-8 -*-
"""配置加载（SPEC §7.1 / §7.2），支持 Qwen（DashScope）与 Tavily 环境变量。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.toml"


class ConfigError(Exception):
    """配置加载错误。"""


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5173


class LLMConfig(BaseModel):
    model: str = "qwen-plus"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    temperature: float = 0.2
    max_tokens: int = 8192


class EmbeddingConfig(BaseModel):
    model: str = "text-embedding-v3"
    api_key: str = ""
    base_url: str = ""


class SearchConfig(BaseModel):
    provider: str = "tavily"
    api_key: str = ""
    max_results: int = 10
    rss_feeds: list[str] = Field(default_factory=list)


class RAGConfig(BaseModel):
    store_path: str = "src/manus/rag/store"
    collection: str = "strategy"
    cases_collection: str = "cases"
    top_k: int = 5
    score_threshold: float = 0.5
    max_context_chars: int = 6000


class WorkflowConfig(BaseModel):
    max_retries: int = 1
    max_deepen_retries: int = 1
    gate_checklist_auto_retry: bool = True
    step_approval_required: bool = True
    lang: str = "zh"
    irreplaceability_threshold: int = 3
    max_run_minutes: int = 15
    news_top_n: int = 5
    hardware_focus_min: int = 4


class FinanceConfig(BaseModel):
    provider: str = "tushare"
    api_key: str = ""
    timeout_sec: int = 10
    cache_ttl_sec: int = 3600
    max_retries: int = 2


class SupplierScreenConfig(BaseModel):
    market: str = "CN"
    board: str = "main"
    exclude_star: bool = True
    exclude_chinext: bool = True
    exclude_bse: bool = True
    exclude_st: bool = True
    min_listing_days: int = 60


class OutputConfig(BaseModel):
    reports_dir: str = "output/reports"
    filename_max_slug: int = 40


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    finance: FinanceConfig = Field(default_factory=FinanceConfig)
    supplier_screen: SupplierScreenConfig = Field(default_factory=SupplierScreenConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def _apply_env_fallback(data: dict[str, Any]) -> dict[str, Any]:
    """环境变量覆盖空配置项。"""
    llm = data.setdefault("llm", {})
    if not llm.get("api_key"):
        llm["api_key"] = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("API_KEY")
            or ""
        )
    if not llm.get("base_url"):
        llm["base_url"] = os.getenv("OPENAI_BASE_URL") or llm.get(
            "base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    emb = data.setdefault("embedding", {})
    if not emb.get("api_key"):
        emb["api_key"] = llm.get("api_key", "")
    if not emb.get("base_url"):
        emb["base_url"] = llm.get("base_url", "")

    search = data.setdefault("search", {})
    if not search.get("api_key"):
        search["api_key"] = os.getenv("TAVILY_API_KEY") or os.getenv("API_KEY") or ""

    finance = data.setdefault("finance", {})
    if not finance.get("api_key"):
        finance["api_key"] = (
            os.getenv("TUSHARE_TOKEN")
            or os.getenv("TUSHARE_API_KEY")
            or os.getenv("TUSHARE_PRO_TOKEN")
            or ""
        )
    return data


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with path.open("rb") as f:
        return tomllib.load(f)


def load_config(
    config_path: Path | str | None = None,
    config_dict: dict[str, Any] | None = None,
) -> AppConfig:
    """从 dict、config.toml 或默认路径加载配置。"""
    if config_dict is not None:
        data = _apply_env_fallback(dict(config_dict))
        return AppConfig.model_validate(data)

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"未找到 config 配置文件: {path}，请复制 config/config.example.toml 为 config.toml")
    data = _apply_env_fallback(_load_toml(path))
    return AppConfig.model_validate(data)


def config_to_dict(cfg: AppConfig | dict[str, Any]) -> dict[str, Any]:
    """统一转为 dict，供 CLI mock 场景使用。"""
    if isinstance(cfg, dict):
        return cfg
    return cfg.model_dump()
