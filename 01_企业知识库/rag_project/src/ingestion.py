"""
FAISS 向量库构建（src/ingestion.py）

主要功能：
- 读取 databases/chunked_reports/{sha1}.json，对每个 chunk 调用 Embedding API
- 构建 FAISS IndexFlatIP 索引并 L2 归一化，写入 databases/vector_dbs/{sha1}.faiss
- 同时写入 {sha1}.faiss.meta.json 元数据

如何调用：
  from pathlib import Path
  from src.ingestion import VectorDBIngestor

  ingestor = VectorDBIngestor(data_root=Path("data/项目知识库"))
  ingestor.process_all_reports()  # 批量建库
  # 通常由 Pipeline.create_vector_dbs() / main.py build-index 调用
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from tqdm import tqdm

from src.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from src.faiss_io import write_faiss_index
from src.multimodal_embedding import embed_chunk


def write_index_metadata(
    path: Path,
    sha1: str,
    doc_id: str,
    num_vectors: int,
) -> dict[str, Any]:
    """写入索引元数据 JSON。"""
    meta = {
        "sha1": sha1,
        "doc_id": doc_id,
        "num_vectors": num_vectors,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": EMBEDDING_DIMENSION,
    }
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


class VectorDBIngestor:
    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.chunked_dir = data_root / "databases/chunked_reports"
        self.vector_dir = data_root / "databases/vector_dbs"

    def build_index_for_report(self, sha1: str) -> dict[str, Any]:
        """为单份 chunked report 构建 FAISS 索引。"""
        report_path = self.chunked_dir / f"{sha1}.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        chunks = report["content"]["chunks"]
        metainfo = report["metainfo"]

        if not chunks:
            return {"sha1": sha1, "skipped": True, "num_vectors": 0}

        vectors: list[list[float]] = []
        for chunk in chunks:
            vec = embed_chunk(
                chunk["text"],
                chunk.get("image_paths", []),
                data_root=self.data_root,
            )
            vectors.append(vec)

        arr = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(arr)
        index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        index.add(arr)

        self.vector_dir.mkdir(parents=True, exist_ok=True)
        faiss_path = self.vector_dir / f"{sha1}.faiss"
        write_faiss_index(index, faiss_path)

        meta_path = self.vector_dir / f"{sha1}.faiss.meta.json"
        return write_index_metadata(
            path=meta_path,
            sha1=sha1,
            doc_id=metainfo.get("doc_id", ""),
            num_vectors=len(chunks),
        )

    def process_all_reports(self) -> int:
        """为 chunked_reports 目录下全部 JSON 建库。"""
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        report_paths = list(self.chunked_dir.glob("*.json"))
        for report_path in tqdm(report_paths, desc="构建 FAISS 向量库"):
            sha1 = report_path.stem
            faiss_path = self.vector_dir / f"{sha1}.faiss"
            if faiss_path.exists():
                continue
            self.build_index_for_report(sha1)
        return len(report_paths)
