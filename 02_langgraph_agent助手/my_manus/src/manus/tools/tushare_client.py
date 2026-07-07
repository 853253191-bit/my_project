# -*- coding: utf-8 -*-
"""Tushare Pro 客户端与 Token 读取。"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd

_pro_api: Any = None
_pro_token: str | None = None
_stock_basic_cache: tuple[float, pd.DataFrame] | None = None
_concept_cache: tuple[float, pd.DataFrame] | None = None
_CACHE_TTL = 3600


class TushareError(Exception):
    pass


def resolve_tushare_token(config: dict[str, Any] | Any | None = None) -> str:
    """从 config 或环境变量读取 Tushare Token。"""
    token = ""
    if config is not None:
        if isinstance(config, dict):
            fin = config.get("finance") or {}
            token = fin.get("api_key") or fin.get("token") or ""
        elif hasattr(config, "finance"):
            token = getattr(config.finance, "api_key", "") or getattr(config.finance, "token", "")
    if not token:
        token = (
            os.getenv("TUSHARE_TOKEN")
            or os.getenv("TUSHARE_API_KEY")
            or os.getenv("TUSHARE_PRO_TOKEN")
            or os.getenv("API_KEY")
            or ""
        )
    if not token:
        raise TushareError("未配置 Tushare Token，请设置环境变量 TUSHARE_TOKEN 或 config.finance.api_key")
    return token


def get_pro_api(config: dict[str, Any] | Any | None = None):
    """获取 Tushare Pro API 实例（单例）。"""
    global _pro_api, _pro_token
    token = resolve_tushare_token(config)
    if _pro_api is not None and _pro_token == token:
        return _pro_api
    import tushare as ts

    ts.set_token(token)
    _pro_api = ts.pro_api()
    _pro_token = token
    return _pro_api


def load_stock_basic(config: dict[str, Any] | Any | None = None) -> pd.DataFrame:
    """加载 A 股基础信息（缓存）。"""
    global _stock_basic_cache
    now = time.time()
    if _stock_basic_cache and now - _stock_basic_cache[0] < _CACHE_TTL:
        return _stock_basic_cache[1]
    pro = get_pro_api(config)
    df = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    if df is None or df.empty:
        raise TushareError("Tushare stock_basic 返回空")
    _stock_basic_cache = (now, df)
    return df


def load_concepts(config: dict[str, Any] | Any | None = None) -> pd.DataFrame:
    """加载概念板块列表（缓存）。"""
    global _concept_cache
    now = time.time()
    if _concept_cache and now - _concept_cache[0] < _CACHE_TTL:
        return _concept_cache[1]
    pro = get_pro_api(config)
    df = pro.concept()
    if df is None:
        df = pd.DataFrame()
    _concept_cache = (now, df)
    return df


def clear_tushare_cache() -> None:
    global _pro_api, _pro_token, _stock_basic_cache, _concept_cache
    _pro_api = None
    _pro_token = None
    _stock_basic_cache = None
    _concept_cache = None
