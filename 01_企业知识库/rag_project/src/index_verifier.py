"""
FAISS 索引完整性校验（src/index_verifier.py）

主要功能：
- 对照 subset.csv 检查每份文档是否有 chunked JSON 与 FAISS 索引
- 校验向量维度是否为 1024；无 chunk 的文档不要求有 .faiss 文件

如何调用：
  from pathlib import Path
  from src.index_verifier import verify_indexes

  report = verify_indexes(Path("data/项目知识库"))
  print(report.passed, report.total)
  # 由 main.py verify-index / build-all 最后一步调用
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import faiss

from src.config import EMBEDDING_DIMENSION
from src.faiss_io import read_faiss_index


@dataclass
class VerificationItem:
    doc_id: str
    sha1: str
    passed: bool
    dimension: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class VerificationReport:
    items: list[VerificationItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def passed(self) -> int:
        return sum(1 for item in self.items if item.passed)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed == self.total


def verify_indexes(data_root: Path) -> VerificationReport:
    """校验 subset.csv 中每份文档的 chunked report 与 FAISS 索引。"""
    subset_path = data_root / "subset.csv"
    chunked_dir = data_root / "databases/chunked_reports"
    vector_dir = data_root / "databases/vector_dbs"

    items: list[VerificationItem] = []

    with subset_path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sha1 = row["sha1"]
            doc_id = row["doc_id"]
            errors: list[str] = []
            dimension = 0
            ok = True

            chunked_path = chunked_dir / f"{sha1}.json"
            has_chunks = False
            if not chunked_path.exists():
                errors.append("chunked report 缺失")
                ok = False
            else:
                chunked = json.loads(chunked_path.read_text(encoding="utf-8"))
                has_chunks = bool(chunked.get("content", {}).get("chunks"))

            faiss_path = vector_dir / f"{sha1}.faiss"
            if has_chunks and not faiss_path.exists():
                errors.append("FAISS 索引缺失")
                ok = False
            elif faiss_path.exists():
                index = read_faiss_index(faiss_path)
                dimension = index.d
                if dimension != EMBEDDING_DIMENSION:
                    errors.append(
                        f"维度错误: 期望 {EMBEDDING_DIMENSION}, 实际 {dimension}"
                    )
                    ok = False

            items.append(VerificationItem(
                doc_id=doc_id,
                sha1=sha1,
                passed=ok,
                dimension=dimension,
                errors=errors,
            ))

    return VerificationReport(items=items)
