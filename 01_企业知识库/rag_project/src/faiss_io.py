"""
FAISS 索引读写（src/faiss_io.py）

主要功能：
- 封装 FAISS 索引的 read/write，解决 Windows 下中文路径无法直接读写的问题
- 写入时先写到 ASCII 临时文件再复制到目标路径

如何调用：
  from pathlib import Path
  import faiss
  from src.faiss_io import read_faiss_index, write_faiss_index

  index = read_faiss_index(Path("databases/vector_dbs/xxx.faiss"))
  write_faiss_index(index, Path("databases/vector_dbs/xxx.faiss"))
  # 由 ingestion.py / retrieval.py / index_verifier.py 内部调用
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import faiss


def write_faiss_index(index: faiss.Index, path: Path | str) -> None:
    """写入 FAISS 索引，规避 Windows 非 ASCII 路径限制。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".faiss")
    os.close(fd)
    try:
        faiss.write_index(index, tmp_path)
        target.write_bytes(Path(tmp_path).read_bytes())
    finally:
        os.unlink(tmp_path)


def read_faiss_index(path: Path | str) -> faiss.Index:
    """读取 FAISS 索引，规避 Windows 非 ASCII 路径限制。"""
    data = Path(path).read_bytes()
    fd, tmp_path = tempfile.mkstemp(suffix=".faiss")
    os.close(fd)
    try:
        Path(tmp_path).write_bytes(data)
        return faiss.read_index(tmp_path)
    finally:
        os.unlink(tmp_path)
