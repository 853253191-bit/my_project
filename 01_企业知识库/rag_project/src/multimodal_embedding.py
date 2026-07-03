"""
多模态 Embedding（src/multimodal_embedding.py）

主要功能：
- 调用 DashScope qwen2.5-vl-embedding，对文本+页图生成 1024 维向量
- embed_chunk：建库时对每个 chunk 向量化
- embed_query：检索时对用户问题向量化

如何调用：
  from pathlib import Path
  from src.multimodal_embedding import embed_chunk, embed_query

  vec = embed_chunk("文本", ["debug_data/04_page_images/.../page_001.png"], data_root=Path("."))
  q_vec = embed_query("用户问题")
  # 需设置环境变量 DASHSCOPE_API_KEY；由 ingestion.py / retrieval.py 调用
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import dashscope
import numpy as np

from src.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL


def to_file_uri(path: Path | str) -> str:
    """将本地路径转为 file:// URI（兼容 Windows）。"""
    p = Path(path).resolve()
    # Windows: file:///D:/path/to/file
    return "file:///" + quote(p.as_posix(), safe="/:")


def require_dashscope_api_key() -> str:
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise ValueError("未设置环境变量 DASHSCOPE_API_KEY")
    return key


def build_multimodal_input(
    text: str,
    image_paths: list[str],
    data_root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """构建 MultiModalEmbedding 输入列表。"""
    mm_input: list[dict[str, Any]] = [{"text": text}]
    for img_path in image_paths:
        p = Path(img_path)
        if not p.is_absolute() and data_root is not None:
            p = data_root / img_path
        mm_input.append({"image": to_file_uri(p)})
    return mm_input


def embed_chunk(
    text: str,
    image_paths: list[str],
    data_root: Optional[Path] = None,
) -> list[float]:
    """对单个 chunk 生成 embedding 向量。"""
    require_dashscope_api_key()
    mm_input = build_multimodal_input(text, image_paths, data_root)
    response = dashscope.MultiModalEmbedding.call(
        model=EMBEDDING_MODEL,
        input=mm_input,
        parameters={"dimension": EMBEDDING_DIMENSION},
    )
    return response["output"]["embeddings"][0]["embedding"]


def embed_query(query: str) -> np.ndarray:
    """对查询文本生成 L2 归一化向量，shape (1, dim)。"""
    require_dashscope_api_key()
    response = dashscope.MultiModalEmbedding.call(
        model=EMBEDDING_MODEL,
        input=[{"text": query}],
        parameters={"dimension": EMBEDDING_DIMENSION},
    )
    vec = np.array(
        response["output"]["embeddings"][0]["embedding"],
        dtype=np.float32,
    ).reshape(1, -1)
    faiss_normalize = vec / np.linalg.norm(vec)
    return faiss_normalize
