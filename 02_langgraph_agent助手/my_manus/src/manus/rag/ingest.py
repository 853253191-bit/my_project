# -*- coding: utf-8 -*-
"""知识库向量入库（strategy + cases，SPEC §5.2）。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from langchain_chroma import Chroma
from langchain_core.documents import Document

from manus.config import PROJECT_ROOT, load_config
from manus.rag.cases_chunk import chunk_cases_document
from manus.rag.chunk import StrategyChunk, chunk_strategy_document
from manus.rag.embeddings import build_embeddings
from manus.rag.store import default_cases_source


def _to_documents(chunks: list[StrategyChunk]) -> list[Document]:
    return [Document(page_content=c.text, metadata=c.metadata) for c in chunks]


def ingest_documents(
    source: Path,
    store_path: Path,
    collection: str,
    chunk_fn: Callable[[Path], list[StrategyChunk]],
) -> int:
    config = load_config()
    chunks = chunk_fn(source)
    docs = _to_documents(chunks)
    store_path.mkdir(parents=True, exist_ok=True)
    Chroma.from_documents(
        documents=docs,
        embedding=build_embeddings(config),
        collection_name=collection,
        persist_directory=str(store_path),
    )
    return len(docs)


def ingest_strategy(source: Path, store_path: Path, collection: str) -> int:
    return ingest_documents(source, store_path, collection, chunk_strategy_document)


def ingest_cases(source: Path, store_path: Path, collection: str) -> int:
    return ingest_documents(source, store_path, collection, chunk_cases_document)


def main() -> None:
    parser = argparse.ArgumentParser(description="ingest 知识库到 Chroma")
    parser.add_argument("--source", default=None, help="源文件路径")
    parser.add_argument("--store", default=None, help="Chroma 持久化目录")
    parser.add_argument(
        "--collection",
        default=None,
        help="collection 名称：strategy（默认）或 cases",
    )
    args = parser.parse_args()
    cfg = load_config()
    store = Path(args.store or PROJECT_ROOT / cfg.rag.store_path)
    collection = args.collection or cfg.rag.collection

    if collection == cfg.rag.cases_collection:
        source = Path(args.source or default_cases_source())
        count = ingest_cases(source, store, collection)
        label = "案例库"
    else:
        source = Path(args.source or PROJECT_ROOT / "knowledge" / "strategy.txt")
        count = ingest_strategy(source, store, collection)
        label = "策略库"

    print(f"{label} ingest 完成: {count} 个分块 <- {source}")
    print(f"collection={collection} store={store}")


if __name__ == "__main__":
    main()
