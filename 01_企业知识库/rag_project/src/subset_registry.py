"""
subset.csv 文档元数据解析（src/subset_registry.py）

主要功能：
- 从 PDF 文件名解析 project_code、doc_id、region、doc_type
- 对 PDF 文件内容计算 sha1 哈希，构建单条文档注册记录
- 无标准项目编号时（政策类 PDF）自动生成 DOC-{sha1前12位} 作为 doc_id

如何调用：
  from pathlib import Path
  from src.subset_registry import build_doc_record, records_to_dataframe

  record = build_doc_record(Path("pdf_reports/某文档.pdf"))
  # 通常由 scripts/generate_subset.py 批量调用
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import SUBSET_CSV_COLUMNS

# SPEC 3.2.4 特殊 doc_type 覆盖（标题关键词无法匹配时）
DOC_TYPE_OVERRIDES: dict[str, str] = {
    "2019-KS-036": "概念性城市设计",
}

# SPEC 3.2.4 十份文档映射表（测试抽样）
SPEC_TABLE: dict[str, dict[str, str]] = {
    "2018-KS-031": {"doc_type": "镇村布局规划", "region": "滨海县"},
    "2019-KS-001": {"doc_type": "概念性城市设计", "region": "昆山市"},
    "2021-KS-0017": {"doc_type": "控规调整", "region": "昆山市"},
    "2021-KS-0032": {"doc_type": "村庄规划", "region": "昆山市"},
}

_ROMAN_TIER_PATTERN = re.compile(r"-[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]-")
_PROJECT_CODE_PATTERN = re.compile(
    r"^(\d{4}(?:-[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]-KS-\d+|(?:-KS-[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]-\d+)))"
)


def parse_project_code(file_name: str) -> str:
    """从 PDF 文件名解析项目编号。"""
    stem = Path(file_name).stem
    match = _PROJECT_CODE_PATTERN.match(stem)
    if not match:
        raise ValueError(f"无法从文件名解析项目编号: {file_name}")
    return match.group(1)


def _extract_year_from_text(text: str) -> int:
    """从文件名或标题中提取年份。"""
    matches = re.findall(r"(20\d{2})", text)
    if matches:
        return int(matches[-1])
    return 0


def _build_generic_doc_record(pdf_path: Path) -> dict[str, Any]:
    """无项目编号时，用文件名与 sha1 构建元数据。"""
    file_name = pdf_path.name
    stem = pdf_path.stem
    sha1 = hashlib.sha1(pdf_path.read_bytes()).hexdigest()
    doc_id = f"DOC-{sha1[:12]}"
    return {
        "doc_id": doc_id,
        "sha1": sha1,
        "file_name": file_name,
        "doc_title": stem,
        "project_code": doc_id,
        "year": _extract_year_from_text(stem),
        "region": infer_region(stem),
        "doc_type": infer_doc_type(stem),
    }


def normalize_doc_id(project_code: str) -> str:
    """将项目编号规范化为 doc_id（去掉罗马数字层级）。"""
    # 2021-Ⅰ-KS-0017 -> 2021-KS-0017
    normalized = re.sub(r"^(\d{4})-[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]-KS-", r"\1-KS-", project_code)
    # 2018-KS-Ⅰ-031 -> 2018-KS-031
    normalized = _ROMAN_TIER_PATTERN.sub("-", normalized)
    return normalized


def infer_region(doc_title: str) -> str:
    """根据文档标题推断所属区域。"""
    if "滨海县" in doc_title:
        return "滨海县"
    if "昆山经济技术开发区" in doc_title:
        return "昆山经济技术开发区"
    if "江苏省" in doc_title:
        return "江苏省"
    return "昆山市"


def infer_doc_type(doc_title: str) -> str:
    """根据文档标题推断文档类型。"""
    if "村庄规划" in doc_title:
        return "村庄规划"
    if "控规调整" in doc_title or "控制性详细规划" in doc_title:
        return "控规调整"
    if "空间发展研究及城市设计" in doc_title:
        return "空间发展研究及城市设计"
    if "空间发展研究" in doc_title:
        return "空间发展研究"
    if "概念性城市设计" in doc_title or "城市设计" in doc_title:
        return "概念性城市设计"
    if "镇村布局" in doc_title:
        return "镇村布局规划"
    if "历史建筑修缮" in doc_title or "文保建筑" in doc_title or "修缮" in doc_title:
        return "历史建筑修缮"
    if "通知" in doc_title:
        return "政策通知"
    if "指南" in doc_title or "导则" in doc_title:
        return "规划指南"
    if "规范" in doc_title or "标准" in doc_title:
        return "技术规范"
    if "成果" in doc_title or "交接" in doc_title:
        return "规划成果"
    return "其他"


def build_doc_record(pdf_path: Path) -> dict[str, Any]:
    """从 PDF 路径构建单条文档元数据记录。"""
    file_name = pdf_path.name
    try:
        project_code = parse_project_code(file_name)
    except ValueError:
        return _build_generic_doc_record(pdf_path)
    doc_id = normalize_doc_id(project_code)
    year = int(project_code[:4])
    stem = pdf_path.stem
    doc_title = stem[len(project_code):].strip()
    sha1 = hashlib.sha1(pdf_path.read_bytes()).hexdigest()
    doc_type = DOC_TYPE_OVERRIDES.get(doc_id, infer_doc_type(doc_title))
    return {
        "doc_id": doc_id,
        "sha1": sha1,
        "file_name": file_name,
        "doc_title": doc_title,
        "project_code": project_code,
        "year": year,
        "region": infer_region(doc_title),
        "doc_type": doc_type,
    }


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """将记录列表转为 DataFrame，列顺序符合 SPEC。"""
    df = pd.DataFrame(records)
    return df[SUBSET_CSV_COLUMNS]


def validate_records_against_spec_table(
    records: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """对照 SPEC 映射表校验 doc_id / doc_type / region。"""
    errors: list[str] = []
    for record in records:
        doc_id = record.get("doc_id", "")
        expected = SPEC_TABLE.get(doc_id)
        if expected is None:
            continue
        if record.get("doc_type") != expected["doc_type"]:
            errors.append(
                f"{doc_id}: doc_type 期望 {expected['doc_type']}, "
                f"实际 {record.get('doc_type')}"
            )
        if record.get("region") != expected["region"]:
            errors.append(
                f"{doc_id}: region 期望 {expected['region']}, "
                f"实际 {record.get('region')}"
            )
    return len(errors) == 0, errors
