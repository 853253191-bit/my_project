# -*- coding: utf-8 -*-
"""strategy.txt 分块（SPEC §5.2）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StrategyChunk:
    text: str
    metadata: dict[str, str]


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def chunk_strategy_document(path: Path | str) -> list[StrategyChunk]:
    """按 ## / ### 标题切分 strategy 文档。"""
    content = Path(path).read_text(encoding="utf-8")
    lines = content.splitlines()
    chunks: list[StrategyChunk] = []
    current_title = "前言"
    current_id = "0"
    current_lines: list[str] = []
    section_idx = 0

    def flush() -> None:
        nonlocal section_idx
        text = "\n".join(current_lines).strip()
        if text:
            chunks.append(
                StrategyChunk(
                    text=text,
                    metadata={"section_id": current_id, "title": current_title},
                )
            )
        section_idx += 1

    for line in lines:
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) >= 2:
            flush()
            current_title = m.group(2).strip()
            current_id = current_title.split("、")[0] if "、" in current_title else str(section_idx)
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()
    return chunks


def format_rag_context(chunks: list[str], max_context_chars: int = 6000) -> str:
    """包装为 Agent 可注入的上下文格式。"""
    header = "=== 策略知识库 ===\n"
    budget = max_context_chars - len(header)
    parts: list[str] = []
    used = 0
    for chunk in chunks:
        piece = chunk.strip()
        if not piece:
            continue
        if used + len(piece) + 2 > budget:
            remain = budget - used
            if remain > 0:
                parts.append(piece[:remain])
            break
        parts.append(piece)
        used += len(piece) + 2
    body = "\n\n".join(parts)
    return header + body
