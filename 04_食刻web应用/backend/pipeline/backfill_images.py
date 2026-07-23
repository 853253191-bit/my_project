# -*- coding: utf-8 -*-
"""为缺少 image_url 的菜谱回填封面图。

策略：
1. 豆果：根据 source_url / id 抓取详情页，解析封面（#banner / upload/caiku）
2. 美食天下：同样按 source_url 补抓（数量很少）
3. 只更新 SQLite image_url，不下载到本地（前端直接用外链）

用法:
  cd backend
  python -m pipeline.backfill_images --limit 20
  python -m pipeline.backfill_images --workers 6
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "src"))
sys.path.insert(0, str(BACKEND_ROOT))

from crawler.base import USER_AGENT  # noqa: E402
from shike.config import load_config, resolve_path  # noqa: E402

logger = logging.getLogger("backfill_images")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def extract_douguo_cover(html: str) -> str:
    """从豆果详情 HTML 提取封面图 URL。"""
    soup = BeautifulSoup(html, "html.parser")
    banner = soup.select_one("#banner")
    if banner and banner.get("data-origin"):
        return str(banner.get("data-origin")).strip()
    img = soup.select_one("#banner img, img.wb100, img[src*='upload/caiku']")
    if img and img.get("src"):
        return str(img.get("src")).strip()
    # 正则兜底
    m = re.search(
        r"https?://[^\"'\s]+/upload/caiku/[^\"'\s]+\.(?:jpg|jpeg|png|webp)",
        html,
        re.I,
    )
    return m.group(0) if m else ""


def extract_meishi_cover(html: str) -> str:
    """从美食天下详情 HTML 提取封面图 URL。"""
    soup = BeautifulSoup(html, "html.parser")
    img = soup.select_one(".recipephoto img, .recipDetail .cover img")
    if img:
        return (img.get("src") or img.get("data-src") or "").strip()
    m = re.search(
        r"https?://[^\"'\s]+meishitx[^\"'\s]+\.(?:jpg|jpeg|png|webp)[^\"'\s]*",
        html,
        re.I,
    )
    return m.group(0) if m else ""


def fetch_cover(client: httpx.Client, recipe_id: str, source_url: str, source_site: str) -> str:
    url = (source_url or "").strip()
    if not url:
        if recipe_id.startswith("douguo_"):
            url = f"https://www.douguo.com/cookbook/{recipe_id.split('_', 1)[1]}.html"
        else:
            return ""
    try:
        resp = client.get(url, timeout=25)
        if resp.status_code != 200:
            logger.warning("HTTP %s %s", resp.status_code, url)
            return ""
        html = resp.text
        if source_site == "douguo" or "douguo.com" in url:
            return extract_douguo_cover(html)
        if source_site == "meishichina" or "meishichina" in url:
            return extract_meishi_cover(html)
        # 未知站点：尝试通用 og:image
        soup = BeautifulSoup(html, "html.parser")
        og = soup.select_one('meta[property="og:image"]')
        return (og.get("content") or "").strip() if og else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("抓取失败 %s: %s", recipe_id, exc)
        return ""


def list_missing(conn: sqlite3.Connection, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT id, title, source_url, source_site
        FROM recipes
        WHERE image_url IS NULL OR trim(image_url) = ''
        ORDER BY rowid ASC
    """
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "source_url": r[2] or "",
            "source_site": r[3] or "",
        }
        for r in rows
    ]


def update_image(conn: sqlite3.Connection, recipe_id: str, image_url: str) -> None:
    conn.execute(
        "UPDATE recipes SET image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (image_url, recipe_id),
    )


def backfill(
    db_path: Path,
    limit: int | None = None,
    workers: int = 4,
    delay: float = 0.2,
) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path), timeout=60)
    missing = list_missing(conn, limit=limit)
    total = len(missing)
    logger.info("待补图: %s 条，workers=%s", total, workers)
    if total == 0:
        conn.close()
        return {"total": 0, "ok": 0, "fail": 0}

    stats = {"total": total, "ok": 0, "fail": 0}
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.douguo.com/"}

    def _one(item: dict[str, Any]) -> tuple[str, str]:
        if delay > 0:
            time.sleep(delay)
        with httpx.Client(
            headers=headers,
            follow_redirects=True,
            timeout=25,
        ) as client:
            url = fetch_cover(
                client,
                item["id"],
                item["source_url"],
                item["source_site"],
            )
        return item["id"], url

    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_one, item): item for item in missing}
        for fut in as_completed(futures):
            item = futures[fut]
            done += 1
            try:
                rid, image_url = fut.result()
            except Exception as exc:  # noqa: BLE001
                stats["fail"] += 1
                logger.warning("任务失败 %s: %s", item["id"], exc)
                continue
            if image_url:
                update_image(conn, rid, image_url)
                stats["ok"] += 1
            else:
                stats["fail"] += 1
            if done % 50 == 0 or done == total:
                conn.commit()
                logger.info(
                    "进度 %s/%s 成功=%s 失败=%s",
                    done,
                    total,
                    stats["ok"],
                    stats["fail"],
                )
                print(
                    f"已处理 {done}/{total} 成功={stats['ok']} 失败={stats['fail']}",
                    flush=True,
                )

    conn.commit()
    conn.close()
    return stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填菜谱封面 image_url")
    p.add_argument("--db", type=str, default="", help="SQLite 路径")
    p.add_argument("--limit", type=int, default=0, help="只处理前 N 条（0=全量）")
    p.add_argument("--workers", type=int, default=6, help="并发数")
    p.add_argument("--delay", type=float, default=0.15, help="每个请求前休眠秒数")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    setup_logging(args.verbose)
    load_dotenv(BACKEND_ROOT / ".env")
    load_dotenv(BACKEND_ROOT.parent / ".env")
    cfg = load_config()
    db_path = Path(args.db) if args.db else resolve_path(cfg.data.sqlite_path)
    if not db_path.is_absolute():
        db_path = (BACKEND_ROOT / db_path).resolve()
    logger.info("DB: %s", db_path)
    stats = backfill(
        db_path=db_path,
        limit=args.limit or None,
        workers=args.workers,
        delay=args.delay,
    )
    msg = f"完成：成功 {stats['ok']} / 失败 {stats['fail']} / 合计 {stats['total']}"
    print(msg, flush=True)
    logger.info(msg)


if __name__ == "__main__":
    main()
