# -*- coding: utf-8 -*-
"""Chroma 向量库加载。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from manus.config import PROJECT_ROOT, AppConfig, load_config


def _as_config(config: AppConfig | dict[str, Any] | None) -> AppConfig:
    if config is None:
        return load_config()
    if isinstance(config, dict):
        return AppConfig.model_validate(config)
    return config


from manus.rag.embeddings import build_embeddings


def get_store(
    config: AppConfig | dict[str, Any] | None = None,
    collection: str | None = None,
) -> "Chroma | None":
    """加载 Chroma collection；目录不存在或依赖缺失时返回 None。"""
    try:
        from langchain_chroma import Chroma
    except ImportError:
        return None

    cfg = _as_config(config)
    store_path = PROJECT_ROOT / cfg.rag.store_path
    if not store_path.is_dir():
        return None
    coll = collection or cfg.rag.collection
    return Chroma(
        collection_name=coll,
        embedding_function=build_embeddings(cfg),
        persist_directory=str(store_path),
    )


def default_cases_source() -> Path:
    """默认案例库路径（SPEC §5.2）。"""
    candidates = [
        PROJECT_ROOT / "Web_Crawler" / "output" / "aleabitoreddit" / "汇总2.md",
        PROJECT_ROOT / "output" / "aleabitoreddit" / "汇总2.md",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]
