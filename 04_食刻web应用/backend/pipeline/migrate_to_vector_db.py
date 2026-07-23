# -*- coding: utf-8 -*-
"""将 SQLite 菜谱迁移到 Chroma 向量库（含硬过滤 metadata）。

依赖:
  pip install chromadb openai python-dotenv

环境变量:
  OPENAI_API_KEY / DASHSCOPE_API_KEY
  OPENAI_BASE_URL（可选，默认走配置里的兼容地址）
  OPENAI_EMBEDDING_MODEL（可选，默认 text-embedding-v3 或 text-embedding-3-small）
  DB_PATH / CHROMA_PATH（可选）

用法:
  cd backend
  python -m pipeline.migrate_to_vector_db
  python -m pipeline.migrate_to_vector_db --batch-size 50
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "src"))
sys.path.insert(0, str(BACKEND_ROOT))

from shike.config import load_config, resolve_path  # noqa: E402

logger = logging.getLogger("migrate_to_vector_db")

COLLECTION_NAME = "recipes"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _json_list_to_text(raw: Any, max_chars: int | None = None) -> str:
    """将 ingredients / steps 的 JSON 展平为自然语言。"""
    if raw is None:
        return ""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text[:max_chars] if max_chars else text
    else:
        data = raw

    parts: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if "name" in item:
                    name = str(item.get("name", "")).strip()
                    amount = str(item.get("amount", "") or "").strip()
                    unit = str(item.get("unit", "") or "").strip()
                    qty = f"{amount}{unit}".strip()
                    parts.append(f"{name}({qty})" if name and qty else name)
                elif "text" in item:
                    parts.append(str(item.get("text", "")).strip())
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item).strip())
    elif isinstance(data, dict):
        parts.append(str(data))
    else:
        parts.append(str(data))

    joined = "；".join(p for p in parts if p)
    if max_chars is not None and len(joined) > max_chars:
        return joined[:max_chars]
    return joined


def build_embedding_text(row: dict[str, Any]) -> str:
    """构造用于向量检索的自然语言文本（不含数值标签）。

    向量检索字段：title / decision_summary / ingredients / steps
    硬过滤字段单独进 metadata，不拼进此文本。
    """
    title = str(row.get("title") or "").strip()
    summary = str(row.get("decision_summary") or "").strip()
    if not summary:
        summary = str(row.get("description") or "").strip()
    ingredients = _json_list_to_text(row.get("ingredients"))
    steps = _json_list_to_text(row.get("steps"), max_chars=100)

    lines = [
        f"菜名：{title}",
        f"简介：{summary}",
        f"食材：{ingredients}",
        f"做法：{steps}",
    ]
    return "\n".join(lines)


def build_metadata(row: dict[str, Any]) -> dict[str, Any]:
    """硬过滤 metadata（字段名与平铺列一致；Chroma 仅支持标量类型）。"""

    def _int_or_default(val: Any, default: int = -1) -> int:
        if val is None or val == "":
            return default
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def _str(val: Any) -> str:
        if val is None:
            return ""
        return str(val)

    return {
        "recipe_id": _str(row.get("id")),
        "title": _str(row.get("title")),
        # 硬过滤字段
        "greasiness": _int_or_default(row.get("greasiness"), -1),
        "spicy_level": _int_or_default(row.get("spicy_level"), -1),
        "cuisine_main": _str(row.get("cuisine_main")),
        "ai_difficulty": _str(row.get("ai_difficulty")),
        "estimated_time": _int_or_default(row.get("estimated_time"), -1),
        "allergens_str": _str(row.get("allergens_str")),
        "diet_labels_str": _str(row.get("diet_labels_str")),
    }


def create_embed_client() -> tuple[OpenAI, str]:
    """创建 Embedding 客户端（兼容 OpenAI / DashScope）。"""
    cfg = load_config()
    api_key = (
        os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("DASHSCOPE_API_KEY", "").strip()
        or cfg.embedding.api_key
        or cfg.llm.api_key
    )
    base_url = (
        os.getenv("OPENAI_BASE_URL", "").strip()
        or cfg.embedding.base_url
    )
    model = (
        os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
        or cfg.embedding.model
        or "text-embedding-v3"
    )
    if not api_key:
        raise RuntimeError("请设置 OPENAI_API_KEY 或 DASHSCOPE_API_KEY")
    if not base_url:
        raise RuntimeError("请设置 OPENAI_BASE_URL")
    logger.info("Embedding: model=%s base_url=%s", model, base_url)
    return OpenAI(api_key=api_key, base_url=base_url), model


def embed_batch(client: OpenAI, model: str, texts: list[str]) -> list[list[float]]:
    """调用 Embedding API；DashScope 单批上限 10，需再切分。"""
    clean = [t if t and t.strip() else " " for t in texts]
    vectors: list[list[float]] = []
    api_batch = 10
    for i in range(0, len(clean), api_batch):
        chunk = clean[i : i + api_batch]
        resp = client.embeddings.create(model=model, input=chunk)
        data = sorted(resp.data, key=lambda x: x.index)
        vectors.extend([item.embedding for item in data])
    return vectors


def load_recipes(db_path: Path) -> list[dict[str, Any]]:
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM recipes ORDER BY rowid ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def reset_collection(chroma_path: Path, collection_name: str = COLLECTION_NAME):
    """开发阶段：清空持久化目录并重建 collection（避免残留 HNSW 段损坏）。

    Windows + chromadb 1.5.x：默认 sync_threshold≈1000 会触发 HNSW 压缩写盘，
    重启/重开后易出现 Error loading hnsw index。将 threshold/batch 调到高于全量，
    让数据留在 WAL，避免损坏的 pickle 持久化。
    """
    import chromadb

    if chroma_path.exists():
        # 只清向量库目录，避免 delete_collection 留下损坏段文件
        shutil.rmtree(chroma_path, ignore_errors=True)
        logger.info("已清空 Chroma 目录: %s", chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "hnsw:space": "cosine",
            "hnsw:batch_size": 20000,
            "hnsw:sync_threshold": 20000,
        },
    )
    return client, collection


def migrate(
    db_path: Path,
    chroma_path: Path,
    batch_size: int = 100,
) -> int:
    recipes = load_recipes(db_path)
    total = len(recipes)
    if total == 0:
        logger.warning("SQLite 中无菜谱数据")
        return 0

    client, model = create_embed_client()
    _, collection = reset_collection(chroma_path)

    processed = 0
    for start in range(0, total, batch_size):
        batch = recipes[start : start + batch_size]
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for row in batch:
            rid = str(row.get("id") or "")
            if not rid:
                continue
            ids.append(rid)
            documents.append(build_embedding_text(row))
            metadatas.append(build_metadata(row))

        if not ids:
            continue

        embeddings = embed_batch(client, model, documents)
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        processed += len(ids)
        msg = f"已处理 {processed}/{total} 条"
        print(msg, flush=True)
        logger.info(msg)

    # 高 sync_threshold 下队列可能长期非空（数据留在 WAL），以 count 可读为准
    ready = _wait_collection_ready(
        chroma_path, collection, expect_count=processed, timeout_sec=120
    )
    done_msg = f"已迁移 {processed} 条菜谱到 Chroma"
    if ready:
        done_msg += f"（校验 count={collection.count()}）"
    else:
        logger.warning("迁移写入完成，但索引校验未通过")
    print(done_msg, flush=True)
    logger.info(done_msg)
    return processed


def _wait_collection_ready(
    chroma_path: Path,
    collection,
    expect_count: int,
    timeout_sec: int = 120,
) -> bool:
    """等待 collection.count() 可用且数量达标。"""
    import sqlite3
    import time

    db = chroma_path / "chroma.sqlite3"
    start = time.time()
    last_q = -1
    while time.time() - start < timeout_sec:
        q = -1
        if db.exists():
            try:
                conn = sqlite3.connect(str(db))
                q = int(conn.execute("SELECT COUNT(*) FROM embeddings_queue").fetchone()[0])
                conn.close()
            except Exception:  # noqa: BLE001
                q = -1
        if q != last_q:
            logger.info("Chroma embeddings_queue 剩余: %s", q)
            last_q = q
        try:
            n = collection.count()
            logger.info("Chroma count=%s（期望 >= %s）", n, expect_count)
            if n >= expect_count:
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("等待索引可读: %s", exc)
        time.sleep(2)
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="迁移菜谱到 Chroma 向量库")
    parser.add_argument("--db", type=str, default="", help="SQLite 路径")
    parser.add_argument("--chroma", type=str, default="", help="Chroma 持久化目录")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="每批 Embedding 条数（默认 100）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    load_dotenv(BACKEND_ROOT / ".env")
    load_dotenv(BACKEND_ROOT.parent / ".env")

    args = parse_args(argv)
    cfg = load_config()

    db_path = Path(
        args.db
        or os.getenv("DB_PATH", "")
        or os.getenv("DATABASE_PATH", "")
        or resolve_path(cfg.data.sqlite_path)
    )
    if not db_path.is_absolute():
        db_path = (BACKEND_ROOT / db_path).resolve()

    chroma_path = Path(
        args.chroma
        or os.getenv("CHROMA_PATH", "")
        or resolve_path(cfg.rag.store_path)
    )
    if not chroma_path.is_absolute():
        chroma_path = (BACKEND_ROOT / chroma_path).resolve()

    logger.info("SQLite: %s", db_path)
    logger.info("Chroma: %s", chroma_path)
    migrate(db_path=db_path, chroma_path=chroma_path, batch_size=max(1, args.batch_size))


if __name__ == "__main__":
    main()
