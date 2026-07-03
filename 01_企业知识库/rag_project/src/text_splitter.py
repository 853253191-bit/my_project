"""
文本分块（src/text_splitter.py）

主要功能：
- 将 merge 后的按页文本按 token 数（默认 400）切分为 chunk
- 为每个 chunk 关联页图路径 image_paths
- 输出 databases/chunked_reports/{sha1}.json，供建库与检索使用

如何调用：
  from pathlib import Path
  from src.text_splitter import TextSplitter

  splitter = TextSplitter(chunk_size=400, chunk_overlap=50)
  splitter.chunk_all_reports(
      merged_dir=Path("debug_data/02_merged_reports"),
      output_dir=Path("databases/chunked_reports"),
      data_root=Path("data/项目知识库"),
  )
  # 通常由 Pipeline.chunk_reports() 调用
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.image_extraction import resolve_image_paths_for_chunk


def _split_text(text: str, chunk_size: int = 400, chunk_overlap: int = 50) -> list[str]:
    """按 token 数分块（LangChain + tiktoken）。"""
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name="gpt-4o",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(text)


def split_merged_report_to_chunks(
    merged_report: dict[str, Any],
    metainfo: dict[str, Any],
    data_root: Path,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> dict[str, Any]:
    """将 merged report 按页分块，并关联 image_paths。"""
    sha1 = metainfo.get("sha1", merged_report.get("metainfo", {}).get("sha1", ""))
    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for page_info in merged_report["content"]["pages"]:
        text = page_info.get("text", "")
        if not text.strip():
            continue
        page_num = page_info["page"]
        for piece in _split_text(text, chunk_size, chunk_overlap):
            if not piece.strip():
                continue
            image_paths = resolve_image_paths_for_chunk(data_root, sha1, page_num)
            chunks.append({
                "chunk_index": chunk_index,
                "page": page_num,
                "text": piece,
                "image_paths": image_paths,
            })
            chunk_index += 1

    return {
        "metainfo": {**metainfo},
        "content": {"chunks": chunks},
    }


def attach_image_paths_to_chunks(
    chunks: list[dict[str, Any]],
    data_root: Path,
    sha1: str,
) -> list[dict[str, Any]]:
    """为已有 chunks 补充 image_paths 字段。"""
    updated: list[dict[str, Any]] = []
    for chunk in chunks:
        new_chunk = dict(chunk)
        page = chunk["page"]
        new_chunk["image_paths"] = resolve_image_paths_for_chunk(
            data_root, sha1, page
        )
        updated.append(new_chunk)
    return updated


def validate_chunked_report(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """校验 chunked report 结构是否符合 SPEC。"""
    errors: list[str] = []
    chunks = report.get("content", {}).get("chunks", [])
    if not chunks:
        errors.append("chunks 为空")
    for i, chunk in enumerate(chunks):
        for field in ("chunk_index", "page", "text", "image_paths"):
            if field not in chunk:
                errors.append(f"chunk[{i}] 缺少字段 {field}")
        if "image_paths" in chunk and not isinstance(chunk["image_paths"], list):
            errors.append(f"chunk[{i}].image_paths 必须为 list")
    return len(errors) == 0, errors


class TextSplitter:
    """批量分块 merged reports。"""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_all_reports(
        self,
        merged_dir: Path,
        output_dir: Path,
        data_root: Path,
    ) -> int:
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for report_path in merged_dir.glob("*.json"):
            merged = json.loads(report_path.read_text(encoding="utf-8"))
            metainfo = dict(merged.get("metainfo") or {})
            if "sha1" not in metainfo:
                metainfo["sha1"] = report_path.stem
            chunked = split_merged_report_to_chunks(
                merged_report=merged,
                metainfo=metainfo,
                data_root=data_root,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            sha1 = metainfo["sha1"]
            out_path = output_dir / f"{sha1}.json"
            out_path.write_text(
                json.dumps(chunked, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            count += 1
        return count

    @staticmethod
    def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
