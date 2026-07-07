# -*- coding: utf-8 -*-
"""LLM 供应商 JSON 字段归一化与容错解析。"""

from __future__ import annotations

import re
from typing import Any

from manus.schemas.models import SupplierProfile
from manus.tools.supplier_screen import parse_ticker_prefix

# LLM 常见别名字段 → SupplierProfile 标准字段
_FIELD_ALIASES: dict[str, str] = {
    "code": "ticker",
    "symbol": "ticker",
    "stock_code": "ticker",
    "ts_code": "ticker",
    "name": "company_name",
    "company": "company_name",
    "stock_name": "company_name",
    "sec_name": "company_name",
    "bottleneck": "bottleneck_id",
    "bn_id": "bottleneck_id",
    "focus_pct": "business_focus_pct",
    "business_pct": "business_focus_pct",
    "coverage": "coverage_level",
    "rationale": "screening_rationale",
    "reason": "screening_rationale",
    "note": "screening_rationale",
}

_MAIN_PREFIXES = ("600", "601", "603", "605", "000", "001", "002")


def format_a_share_ticker(code: str) -> str:
    """6 位代码 → 600519.SH / 000001.SZ。"""
    digits = re.sub(r"\D", "", str(code or ""))[:6]
    if len(digits) != 6:
        return str(code or "").strip().upper()
    if digits.startswith(("600", "601", "603", "605")):
        return f"{digits}.SH"
    if digits.startswith(("000", "001", "002")):
        return f"{digits}.SZ"
    return digits


def normalize_ticker(raw: Any) -> str:
    """统一 ticker：支持纯 6 位码或带后缀。"""
    text = str(raw or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        code, suffix = text.split(".", 1)
        digits = re.sub(r"\D", "", code)[:6]
        if suffix in ("SH", "SZ") and len(digits) == 6:
            return f"{digits}.{suffix}"
        return format_a_share_ticker(digits)
    return format_a_share_ticker(text)


def normalize_supplier_dict(
    raw: dict[str, Any],
    *,
    default_bottleneck_id: str = "bn-unknown",
) -> dict[str, Any]:
    """将 LLM / akshare 混合格式转为 SupplierProfile 可校验 dict。"""
    merged: dict[str, Any] = {}
    for key, val in raw.items():
        target = _FIELD_ALIASES.get(key, key)
        if target not in merged or merged[target] in (None, ""):
            merged[target] = val

    ticker = normalize_ticker(merged.get("ticker") or merged.get("code") or merged.get("symbol"))
    if ticker:
        merged["ticker"] = ticker

    name = str(merged.get("company_name") or merged.get("name") or "").strip()
    if name:
        merged["company_name"] = name

    if not merged.get("bottleneck_id"):
        merged["bottleneck_id"] = default_bottleneck_id

    if merged.get("business_focus_pct") is None:
        merged["business_focus_pct"] = 50.0
    else:
        try:
            merged["business_focus_pct"] = float(merged["business_focus_pct"])
        except (TypeError, ValueError):
            merged["business_focus_pct"] = 50.0

    coverage = str(merged.get("coverage_level") or "medium").lower()
    if coverage not in ("high", "medium", "low"):
        coverage = "medium"
    merged["coverage_level"] = coverage

    risks = merged.get("risks")
    if not risks:
        risks = merged.get("risk")
    if isinstance(risks, str):
        risks = [risks]
    if not isinstance(risks, list) or not risks:
        risks = ["待人工复核产业链匹配度"]
    merged["risks"] = [str(r) for r in risks if r]

    merged.setdefault("market", "CN")
    merged.setdefault("listing_board", "main")
    merged.setdefault("is_st", False)
    merged.setdefault("catalysts", [])
    merged.setdefault("screening_rationale", merged.get("screening_rationale") or "产业链环节匹配")

    prefix = parse_ticker_prefix(merged.get("ticker", ""))
    if prefix and not prefix.startswith(_MAIN_PREFIXES):
        merged["_reject_reason"] = "not_main_board_prefix"

    if not merged.get("company_name") and not merged.get("ticker"):
        merged["_reject_reason"] = "missing_ticker_and_name"

    return merged


def parse_supplier_profiles(
    raw_list: list[dict[str, Any]] | list[Any],
    *,
    default_bottleneck_id: str = "bn-unknown",
) -> tuple[list[SupplierProfile], list[str]]:
    """逐条解析，单条失败不拖垮整批。"""
    profiles: list[SupplierProfile] = []
    errors: list[str] = []
    for idx, item in enumerate(raw_list or []):
        if not isinstance(item, dict):
            errors.append(f"supplier_skip_{idx}: 非 dict")
            continue
        normalized = normalize_supplier_dict(item, default_bottleneck_id=default_bottleneck_id)
        reject = normalized.pop("_reject_reason", None)
        if reject:
            label = normalized.get("ticker") or normalized.get("company_name") or f"idx{idx}"
            errors.append(f"supplier_skip_{label}: {reject}")
            continue
        try:
            profiles.append(SupplierProfile.model_validate(normalized))
        except Exception as exc:
            label = normalized.get("ticker") or normalized.get("company_name") or f"idx{idx}"
            errors.append(f"supplier_parse_{label}: {exc}")
    return profiles, errors


def default_bottleneck_id_from_state(state: dict[str, Any]) -> str:
    for bn in state.get("bottlenecks") or []:
        if isinstance(bn, dict) and bn.get("id"):
            return str(bn["id"])
    return "bn-unknown"


SUPPLIER_JSON_SCHEMA_HINT = """
输出严格 JSON，suppliers 为数组。每个元素必须包含以下字段（不要使用 code/name 别名）：
{
  "suppliers": [
    {
      "bottleneck_id": "bn-1",
      "company_name": "长电科技",
      "ticker": "600584.SH",
      "market": "CN",
      "listing_board": "main",
      "is_st": false,
      "business_focus_pct": 75,
      "coverage_level": "high",
      "risks": ["客户集中度", "周期波动"],
      "catalysts": ["先进封装扩产"],
      "screening_rationale": "国内先进封装龙头，与 HBM/存储产业链相关"
    }
  ]
}
仅允许沪深主板（600/601/603/605/000/001/002 开头），禁止 688/300/8 开头及 ST。
"""
