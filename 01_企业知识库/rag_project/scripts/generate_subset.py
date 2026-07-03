"""
从 pdf_reports/ 扫描 PDF 并生成文档注册表 subset.csv（scripts/generate_subset.py）

主要功能：
- 将 data/项目知识库 根目录下误放的 PDF 复制到 pdf_reports/
- 对每个 PDF 计算 sha1、解析 doc_id/doc_title/region/doc_type 等元数据
- 输出 subset.csv，供后续 parse-pdfs、建库、检索使用

如何调用（在 rag_project 根目录）：
  cd 01_企业知识库/rag_project
  python scripts/generate_subset.py

典型流程：
  1. 将 PDF 放入 data/项目知识库/pdf_reports/
  2. 运行本脚本生成 subset.csv
  3. 在 data/项目知识库 下执行 python ../../main.py build-all
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.subset_registry import build_doc_record, records_to_dataframe

DATA_ROOT = PROJECT_ROOT / "data" / "项目知识库"
PDF_DIR = DATA_ROOT / "pdf_reports"
SUBSET_PATH = DATA_ROOT / "subset.csv"


def migrate_pdfs() -> None:
    """将根目录 PDF 迁移至 pdf_reports/。"""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for pdf in DATA_ROOT.glob("*.pdf"):
        target = PDF_DIR / pdf.name
        if not target.exists():
            shutil.copy2(pdf, target)
            print(f"已复制: {pdf.name}")


def generate_subset() -> pd.DataFrame:
    migrate_pdfs()
    records = []
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        record = build_doc_record(pdf_path)
        records.append(record)
        print(f"  {record['doc_id']} <- {pdf_path.name}")
    df = records_to_dataframe(records)
    df.to_csv(SUBSET_PATH, index=False, encoding="utf-8-sig")
    print(f"已写入 {SUBSET_PATH}，共 {len(df)} 条记录")
    return df


if __name__ == "__main__":
    generate_subset()
