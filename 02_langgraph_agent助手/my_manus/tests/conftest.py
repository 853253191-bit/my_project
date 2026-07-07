# -*- coding: utf-8 -*-
"""pytest 全局 fixture：路径、示例配置、PipelineState 样例。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

# 项目根目录（my_manus/）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_STRATEGY = PROJECT_ROOT / "knowledge" / "strategy.txt"
CONFIG_EXAMPLE = PROJECT_ROOT / "config" / "config.example.toml"


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def strategy_txt_path(project_root: Path) -> Path:
    path = project_root / "knowledge" / "strategy.txt"
    assert path.is_file(), f"缺少知识库文件: {path}"
    return path


@pytest.fixture
def tmp_runs_dir(tmp_path: Path) -> Path:
    """临时 runs 目录，用于 RunManager 持久化测试。"""
    runs = tmp_path / "runs"
    runs.mkdir()
    return runs


@pytest.fixture
def minimal_config_dict() -> dict[str, Any]:
    """对齐 SPEC §7.1 的最小配置字典。"""
    return {
        "server": {"host": "127.0.0.1", "port": 5173},
        "llm": {
            "model": "gpt-4o",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "temperature": 0.2,
            "max_tokens": 8192,
        },
        "embedding": {"model": "text-embedding-3-small", "api_key": "", "base_url": ""},
        "search": {"provider": "tavily", "api_key": "test", "max_results": 10, "rss_feeds": []},
        "rag": {
            "store_path": "src/manus/rag/store",
            "collection": "strategy",
            "cases_collection": "cases",
            "top_k": 5,
            "score_threshold": 0.5,
            "max_context_chars": 6000,
        },
        "workflow": {
            "max_retries": 1,
            "max_deepen_retries": 1,
            "gate_checklist_auto_retry": True,
            "step_approval_required": True,
            "lang": "zh",
            "irreplaceability_threshold": 3,
            "max_run_minutes": 15,
            "news_top_n": 5,
            "hardware_focus_min": 4,
        },
        "finance": {"provider": "tushare", "api_key": "test-token", "timeout_sec": 10, "cache_ttl_sec": 3600, "max_retries": 2},
        "supplier_screen": {
            "market": "CN",
            "board": "main",
            "exclude_star": True,
            "exclude_chinext": True,
            "exclude_bse": True,
            "exclude_st": True,
            "min_listing_days": 60,
        },
        "output": {"reports_dir": "output/reports", "filename_max_slug": 40},
    }


@pytest.fixture(autouse=True)
def _clear_finance_cache():
    from manus.tools.finance_lookup import clear_finance_cache
    from manus.tools.tushare_client import clear_tushare_cache

    clear_finance_cache()
    clear_tushare_cache()
    yield
    clear_finance_cache()
    clear_tushare_cache()


@pytest.fixture
def sample_news_item() -> dict[str, Any]:
    return {
        "id": "news-001",
        "title": "CPO 1.6T 量产进展",
        "summary": "某厂商宣布 1.6T 光模块量产时间表提前，产业链上游 InP 基板与 CW 激光需求升温。",
        "source": "TestWire",
        "url": "https://example.com/cpo-16t",
        "published_at": "2026-07-07T08:00:00Z",
        "heat_score": 0.82,
        "relevance_tags": ["CPO", "Photonics"],
        "hardware_focus": True,
        "hardware_tags": ["CPO", "Photonics"],
        "research_hint": "可拆解 FAU / InP 基板 / CW 激光",
        "why_selected": "硬件向、24h 内、与 AI 互连相关",
    }


@pytest.fixture
def filled_pipeline_state_dict(sample_news_item: dict[str, Any]) -> dict[str, Any]:
    """含 Phase1+Phase2 各阶段字段的完整 state 样例，用于 field_clear / gates 测试。"""
    return {
        "run_id": "run-test-001",
        "run_date": "2026-07-07",
        "phase": "research",
        "status": "awaiting_step_approval",
        "pending_approval_step": 3,
        "step_output_summary": "完成断供测试",
        "approval_hints": None,
        "news_items": [sample_news_item],
        "selected_news_id": sample_news_item["id"],
        "selected_news_item": sample_news_item,
        "component_node": {
            "news_id": sample_news_item["id"],
            "decomposition_depth": 3,
            "terminal_demand": {
                "description": "AI 算力扩张",
                "outlook_2_3y": "continue",
                "backing": "巨头 capex",
            },
            "components": [
                {
                    "name": "光引擎",
                    "category": "interconnect",
                    "value_share": "high",
                    "growth_driver": "CPO 渗透率",
                    "upstream_hints": ["InP 基板"],
                }
            ],
            "horizontal_branches": [
                {"type": "upstream_material", "node": "InP 基板", "rationale": "光模块上游"}
            ],
        },
        "gate_outlook_result": "continue",
        "bottlenecks": [
            {
                "id": "bn-1",
                "component": "光引擎",
                "bottleneck_name": "InP 基板",
                "layer": "material",
                "traits": {
                    "mandatory": "true",
                    "oligopoly": "true",
                    "slow_expansion": "true",
                    "low_coverage": "unknown",
                },
                "mismatch_hypothesis": "需求跳升供给跟不上",
                "evidence": ["行业报告"],
            }
        ],
        "ripple_notes": "关注出口管制连带",
        "validations": [],
        "red_team": None,
        "checklist_gate": None,
        "confidence": "high",
        "suppliers": [],
        "suppliers_excluded": [],
        "errors": [],
        "final_report_md": "",
        "report_output_path": None,
        "agent6_mode": "generate",
        "rerun_from_step": None,
        "rag_contexts": {},
    }


@pytest.fixture
def sample_supplier_main() -> dict[str, Any]:
    return {
        "bottleneck_id": "bn-1",
        "company_name": "贵州茅台",
        "ticker": "600519.SH",
        "market": "CN",
        "listing_board": "main",
        "is_st": False,
        "business_focus_pct": 95.0,
        "coverage_level": "high",
        "risks": ["估值偏高"],
        "catalysts": ["产能扩张"],
    }
