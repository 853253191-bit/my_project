# -*- coding: utf-8 -*-
"""配置加载，支持 TOML 与环境变量。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.toml"


class ConfigError(Exception):
    """配置加载错误。"""


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


class LLMConfig(BaseModel):
    model: str = "qwen-plus"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    temperature: float = 0.3
    max_tokens: int = 4096


class EmbeddingConfig(BaseModel):
    model: str = "text-embedding-v3"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class RerankConfig(BaseModel):
    model: str = "gte-rerank"
    enabled: bool = True


class RAGConfig(BaseModel):
    store_path: str = "data/chroma_recipes"
    collection: str = "recipes"
    top_k: int = 20
    rerank_top_n: int = 5
    max_context_chars: int = 8000


class DataConfig(BaseModel):
    sqlite_path: str = "data/sqlite/recipes.db"
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"


class WeatherConfig(BaseModel):
    provider: str = "amap"
    api_key: str = ""


class SessionConfig(BaseModel):
    max_history: int = 10
    ttl_hours: int = 24


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore
    return tomllib.loads(path.read_text(encoding="utf-8"))


# 部署模板里的占位符，不能当作有效 API Key
_API_KEY_PLACEHOLDERS = frozenset({
    "",
    "请填写",
    "你的API密钥",
    "你的真实密钥",
    "your-api-key",
    "changeme",
})


def resolve_llm_api_key(cfg: AppConfig | None = None) -> str:
    """按优先级读取可用 LLM Key，自动跳过「请填写」等占位符。"""
    candidates = [
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("DASHSCOPE_API_KEY", ""),
        (cfg.llm.api_key if cfg is not None else ""),
    ]
    for raw in candidates:
        key = (raw or "").strip()
        if not key or key in _API_KEY_PLACEHOLDERS:
            continue
        if key.startswith("你的") or key.startswith("请"):
            continue
        return key
    return ""


def _apply_env_overrides(cfg: AppConfig) -> AppConfig:
    data = cfg.model_dump()
    # 统一解析 Key，自动跳过「请填写」等占位符（避免无效 OPENAI_API_KEY 覆盖有效 DashScope）
    api_key = resolve_llm_api_key(cfg)
    if api_key:
        data["llm"]["api_key"] = api_key
        data["embedding"]["api_key"] = api_key
    if os.getenv("OPENAI_BASE_URL"):
        data["llm"]["base_url"] = os.environ["OPENAI_BASE_URL"]
        data["embedding"]["base_url"] = os.environ["OPENAI_BASE_URL"]
    if os.getenv("OPENAI_MODEL"):
        data["llm"]["model"] = os.environ["OPENAI_MODEL"]
    if os.getenv("OPENAI_EMBEDDING_MODEL"):
        data["embedding"]["model"] = os.environ["OPENAI_EMBEDDING_MODEL"]
    if os.getenv("AMAP_API_KEY"):
        data["weather"]["api_key"] = os.environ["AMAP_API_KEY"]
    if os.getenv("DATABASE_PATH"):
        data["data"]["sqlite_path"] = os.environ["DATABASE_PATH"]
    if os.getenv("DB_PATH"):
        data["data"]["sqlite_path"] = os.environ["DB_PATH"]
    if os.getenv("CHROMA_PATH"):
        data["rag"]["store_path"] = os.environ["CHROMA_PATH"]
    if os.getenv("CORS_ORIGINS"):
        data["server"]["cors_origins"] = [
            o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()
        ]
    return AppConfig.model_validate(data)


def load_config(config_path: Path | str | None = None) -> AppConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_file():
        example = PROJECT_ROOT / "config" / "config.example.toml"
        if example.is_file():
            path = example
        else:
            return _apply_env_overrides(AppConfig())
    raw = _load_toml(path)
    cfg = AppConfig.model_validate(raw)
    return _apply_env_overrides(cfg)


def resolve_path(relative: str) -> Path:
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p


def require_api_key(cfg: AppConfig) -> str:
    key = resolve_llm_api_key(cfg)
    if not key:
        raise ConfigError("未配置 DASHSCOPE_API_KEY / OPENAI_API_KEY")
    return key
