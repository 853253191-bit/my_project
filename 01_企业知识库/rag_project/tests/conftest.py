"""
pytest 公共 fixture 与测试数据（tests/conftest.py）

主要功能：
- 提供 tmp_data_root、fixtures_dir、sample_merged_report 等共享 fixture
- 定义 PROJECT_ROOT、DATA_ROOT 路径常量，供各阶段测试复用

如何调用（不直接运行本文件，由 pytest 自动加载）：
  cd 01_企业知识库/rag_project
  pytest tests/ -v                    # 运行全部测试
  pytest tests/phase1 -m phase1 -v    # 仅阶段一
  pytest tests/conftest.py -v         # 不会单独执行，fixture 随测试加载
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# 项目根目录：rag_project/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "项目知识库"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def data_root() -> Path:
    return DATA_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_merged_report(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "sample_merged_report.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def sample_chunked_report(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "sample_chunked_report.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def tmp_data_root(tmp_path: Path) -> Path:
    """临时数据目录，模拟 data/项目知识库 结构（目录名用 ASCII 以兼容 Windows FAISS）。"""
    root = tmp_path / "kb_data"
    for sub in [
        "pdf_reports",
        "debug_data/01_parsed_reports",
        "debug_data/02_merged_reports",
        "debug_data/03_reports_markdown",
        "debug_data/04_page_images",
        "databases/chunked_reports",
        "databases/vector_dbs",
    ]:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root
