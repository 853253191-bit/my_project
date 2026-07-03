"""
阶段一：subset.csv 元数据解析测试（tests/phase1/test_subset_registry.py）

主要功能：
- 测试从 PDF 文件名解析 project_code、doc_id（含罗马数字规范化）
- 测试 region、doc_type 关键词推断
- 测试 build_doc_record 字段完整性与 sha1 计算
- 对照 SPEC 3.2.4 映射表校验

如何调用：
  cd 01_企业知识库/rag_project
  pytest tests/phase1/test_subset_registry.py -v
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.subset_registry import (
    build_doc_record,
    infer_doc_type,
    infer_region,
    normalize_doc_id,
    parse_project_code,
    records_to_dataframe,
    validate_records_against_spec_table,
)


@pytest.mark.phase1
class TestParseProjectCode:
    @pytest.mark.parametrize(
        "file_name,expected",
        [
            ("2018-KS-Ⅰ-031 滨海县县域镇村布局规划.pdf", "2018-KS-Ⅰ-031"),
            ("2021-Ⅰ-KS-0017   D06单元控规调整.pdf", "2021-Ⅰ-KS-0017"),
        ],
    )
    def test_parse_project_code_from_filename(self, file_name: str, expected: str):
        assert parse_project_code(file_name) == expected


@pytest.mark.phase1
class TestNormalizeDocId:
    @pytest.mark.parametrize(
        "project_code,expected",
        [
            ("2018-KS-Ⅰ-031", "2018-KS-031"),
            ("2021-Ⅰ-KS-0017", "2021-KS-0017"),
            ("2019-KS-Ⅳ-036", "2019-KS-036"),
        ],
    )
    def test_normalize_doc_id(self, project_code: str, expected: str):
        assert normalize_doc_id(project_code) == expected


@pytest.mark.phase1
class TestInferRegion:
    @pytest.mark.parametrize(
        "doc_title,expected",
        [
            ("滨海县县域镇村布局规划", "滨海县"),
            ("昆山经济技术开发区东部新城核心区空间发展研究及城市设计", "昆山经济技术开发区"),
            ("D06单元控规调整", "昆山市"),
        ],
    )
    def test_infer_region(self, doc_title: str, expected: str):
        assert infer_region(doc_title) == expected


@pytest.mark.phase1
class TestInferDocType:
    @pytest.mark.parametrize(
        "doc_title,expected",
        [
            ("武城村、凤凰村行政村实用性村庄规划", "村庄规划"),
            ("D06单元控规调整", "控规调整"),
            ("S1沿线站台周边区域概念性城市设计", "概念性城市设计"),
            ("东部新城核心区空间发展研究及城市设计", "空间发展研究及城市设计"),
            ("蓬朗老街建设和文保建筑及历史建筑修缮二期工程", "历史建筑修缮"),
        ],
    )
    def test_infer_doc_type(self, doc_title: str, expected: str):
        assert infer_doc_type(doc_title) == expected


@pytest.mark.phase1
class TestBuildDocRecord:
    def test_build_doc_record_fields(self, tmp_path: Path):
        pdf_dir = tmp_path / "pdf_reports"
        pdf_dir.mkdir()
        file_name = "2021-Ⅰ-KS-0017   D06单元控规调整.pdf"
        pdf_path = pdf_dir / file_name
        pdf_path.write_bytes(b"%PDF-1.4 dummy")

        record = build_doc_record(pdf_path)

        assert record["file_name"] == file_name
        assert record["doc_id"] == "2021-KS-0017"
        assert record["project_code"] == "2021-Ⅰ-KS-0017"
        assert record["year"] == 2021
        assert record["doc_title"] == "D06单元控规调整"
        assert record["region"] == "昆山市"
        assert record["doc_type"] == "控规调整"
        assert record["sha1"] == hashlib.sha1(pdf_path.read_bytes()).hexdigest()

    def test_records_to_dataframe_columns(self, tmp_path: Path):
        pdf_dir = tmp_path / "pdf_reports"
        pdf_dir.mkdir()
        p = pdf_dir / "2021-Ⅰ-KS-0017   D06单元控规调整.pdf"
        p.write_bytes(b"x")
        df = records_to_dataframe([build_doc_record(p)])
        assert list(df.columns) == [
            "doc_id", "sha1", "file_name", "doc_title",
            "project_code", "year", "region", "doc_type",
        ]


@pytest.mark.phase1
class TestSpecMappingTable:
    """对照 SPEC 3.2.4 十份文档映射表。"""

    SPEC_ROWS = [
        ("2018-KS-031", "镇村布局规划", "滨海县"),
        ("2019-KS-001", "概念性城市设计", "昆山市"),
        ("2021-KS-0017", "控规调整", "昆山市"),
        ("2021-KS-0032", "村庄规划", "昆山市"),
    ]

    @pytest.mark.parametrize("doc_id,doc_type,region", SPEC_ROWS)
    def test_validate_spec_table_subset(self, doc_id: str, doc_type: str, region: str):
        ok, errors = validate_records_against_spec_table(
            [{"doc_id": doc_id, "doc_type": doc_type, "region": region}]
        )
        assert ok, errors
