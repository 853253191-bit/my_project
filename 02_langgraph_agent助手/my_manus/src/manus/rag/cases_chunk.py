# -*- coding: utf-8 -*-
"""汇总2.md 等实战案例分块（SPEC §5.2）。"""

from __future__ import annotations

import re
from pathlib import Path

from manus.rag.chunk import StrategyChunk

_POST_ID_RE = re.compile(r"帖子 ID\*\*:\s*`([^`]+)`")
_POST_TIME_RE = re.compile(r"^## 帖子 \d+ \| (.+)$", re.MULTILINE)


def chunk_cases_document(path: Path | str) -> list[StrategyChunk]:
    """按 --- 帖子边界切分案例库文档。"""
    content = Path(path).read_text(encoding="utf-8")
    segments = re.split(r"\n---\n", content)
    chunks: list[StrategyChunk] = []

    for seg in segments:
        text = seg.strip()
        if not text or "## 帖子" not in text:
            continue

        post_id = ""
        m_id = _POST_ID_RE.search(text)
        if m_id:
            post_id = m_id.group(1)

        created_at = ""
        m_time = _POST_TIME_RE.search(text)
        if m_time:
            created_at = m_time.group(1).strip()

        chunks.append(
            StrategyChunk(
                text=text,
                metadata={
                    "source": "aleabitoreddit",
                    "post_id": post_id,
                    "created_at": created_at,
                    "title": created_at,
                },
            )
        )
    return chunks


def format_cases_context(chunks: list[str], max_context_chars: int = 6000) -> str:
    """包装案例库检索结果为 prompt 片段。"""
    header = "=== 实战案例库 ===\n"
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
    return header + "\n\n".join(parts)
