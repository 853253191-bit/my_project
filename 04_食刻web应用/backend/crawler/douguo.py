# -*- coding: utf-8 -*-
"""豆果美食爬虫（API 列表 + API/HTML 详情）。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from crawler.base import (
    CrawlRecipe,
    JsonRecipeStore,
    map_tags,
    parse_amount_unit,
    parse_minutes,
    sleep_interval,
    USER_AGENT,
)
from crawler.douguo_api_html import parse_douguo_api_html
from crawler.douguo_html import parse_douguo_html

logger = logging.getLogger(__name__)

API_BASE = "https://api.douguo.net"
DETAIL_URL = "https://www.douguo.com/cookbook/{recipe_id}.html"

# 默认搜索关键词（也可从 flatcatalogs 自动扩展）
DEFAULT_KEYWORDS = [
    "红烧肉", "番茄炒蛋", "宫保鸡丁", "麻婆豆腐", "清蒸鱼", "可乐鸡翅",
    "酸辣土豆丝", "冬瓜排骨汤", "皮蛋瘦肉粥", "蔬菜沙拉", "牛排", "披萨",
    "意大利面", "咖喱", "寿司", "蛋糕", "饼干", "豆浆", "油条", "饺子",
    "包子", "面条", "牛肉", "鸡肉", "猪肉", "虾", "豆腐", "土豆", "番茄",
    "鸡蛋", "青椒", "茄子", "黄瓜", "排骨", "鸡翅", "鱼", "虾", "菌菇",
]


class DouguoCrawler:
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=30,
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def fetch_keywords(self) -> list[str]:
        """从 flatcatalogs 提取标签关键词，并合并默认关键词。"""
        resp = self.client.post(f"{API_BASE}/recipe/flatcatalogs", data={"client": "4", "_vs": "0"})
        resp.raise_for_status()
        keywords: list[str] = []
        for cat in resp.json().get("result", {}).get("catalogs", []):
            for tag in cat.get("tags", []):
                name = tag.get("t", "").strip()
                if name and name not in keywords:
                    keywords.append(name)
        for kw in DEFAULT_KEYWORDS:
            if kw not in keywords:
                keywords.append(kw)
        return keywords or DEFAULT_KEYWORDS

    def search_recipe_ids(self, keyword: str, max_pages: int = 3) -> list[int]:
        """按关键词搜索菜谱 ID。"""
        ids: list[int] = []
        page_size = 20
        for page in range(max_pages):
            start = page * page_size
            end = start + page_size
            data = {
                "client": "4",
                "keyword": keyword,
                "order": "0",
                "_vs": "11102",
                "type": "0",
                "auto_play_mode": "2",
            }
            resp = self.client.post(f"{API_BASE}/recipe/v2/search/{start}/{end}", data=data)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            items = result.get("list", []) if isinstance(result, dict) else []
            if not items:
                break
            for item in items:
                if item.get("type") == 13 and item.get("r", {}).get("id"):
                    ids.append(int(item["r"]["id"]))
            sleep_interval(self.delay)
        return ids

    def fetch_detail(self, recipe_id: int) -> dict[str, Any] | None:
        """获取菜谱详情（API 优先，网页 HTML 作为补充）。"""
        url = DETAIL_URL.format(recipe_id=recipe_id)
        ext = json.dumps({"query": {"id": recipe_id, "kw": "", "idx": "1", "src": "2801", "type": "13"}})
        data = {"client": "4", "author_id": "0", "_vs": "2801", "_ext": ext}

        resp = self.client.post(f"{API_BASE}/recipe/detail/{recipe_id}", data=data)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "json" in content_type:
                body = resp.json()
                if body.get("state") == "success":
                    recipe = body.get("result", {}).get("recipe")
                    if recipe:
                        return recipe
            parsed = parse_douguo_api_html(resp.text, recipe_id, url)
            if parsed and parsed.get("cookstep"):
                return parsed

        page = self.client.get(url)
        if page.status_code == 200:
            parsed = parse_douguo_html(page.text, recipe_id, url)
            if parsed:
                return parsed
        return None

    def parse_recipe(self, recipe_id: int, raw: dict[str, Any]) -> CrawlRecipe | None:
        title = (raw.get("title") or raw.get("name") or "").strip()
        if not title:
            return None

        description = (raw.get("cookstory") or raw.get("cookstorys") or "").strip()
        tips = (raw.get("tips") or "").strip()
        if tips:
            description = f"{description}\n\n小贴士：{tips}".strip()

        ingredients: list[dict[str, str]] = []
        for group_key in ("major", "minor"):
            for item in raw.get(group_key) or []:
                name = (item.get("title") or "").strip()
                note = (item.get("note") or "").strip()
                amount, unit = parse_amount_unit(note)
                if name:
                    ingredients.append({"name": name, "amount": amount, "unit": unit})

        steps: list[dict[str, Any]] = []
        for step in raw.get("cookstep") or []:
            text = (step.get("content") or "").strip()
            if not text:
                continue
            img = step.get("image") or step.get("thumb") or ""
            steps.append({
                "order": step.get("position") or len(steps) + 1,
                "text": text,
                "image_url": img,
            })

        if len(ingredients) < 2 or len(steps) < 2:
            return None

        raw_tags: list[str] = []
        for key in ("recipe_tags", "tags", "recipe_list_tags"):
            val = raw.get(key)
            if isinstance(val, list):
                for t in val:
                    if isinstance(t, str):
                        raw_tags.append(t)
                    elif isinstance(t, dict):
                        raw_tags.append(t.get("name") or t.get("t") or "")
            elif isinstance(val, str) and val:
                raw_tags.append(val)

        tag_map = map_tags(raw_tags, title, description)
        cook_time = raw.get("cook_time") or raw.get("cooktime") or ""
        difficulty = raw.get("cook_difficulty") or raw.get("burden") or "简单"

        return CrawlRecipe(
            recipe_id=f"douguo_{recipe_id}",
            title=title,
            description=description,
            cuisine=raw_tags[0] if raw_tags else "家常菜",
            difficulty=str(difficulty),
            cook_minutes=parse_minutes(str(cook_time)),
            servings=_parse_servings(raw.get("peoplenum") or raw.get("servings")),
            mood_tags=tag_map["mood_tags"],
            taste_tags=tag_map["taste_tags"],
            health_tags=tag_map["health_tags"],
            weather_tags=tag_map["weather_tags"],
            ingredients=ingredients,
            steps=steps,
            source_url=DETAIL_URL.format(recipe_id=recipe_id),
            source_site="douguo",
            image_url=raw.get("image") or raw.get("photo_path") or raw.get("thumb_path") or "",
            tags=[t for t in raw_tags if t],
        )

    def discover_related_ids(self, recipe_id: int) -> list[int]:
        """从详情页 HTML 提取相关菜谱 ID。"""
        resp = self.client.get(DETAIL_URL.format(recipe_id=recipe_id))
        if resp.status_code != 200:
            return []
        return [int(x) for x in set(re.findall(r"/cookbook/(\d+)\.html", resp.text))]

    def crawl(
        self,
        store: JsonRecipeStore,
        max_recipes: int = 100,
        keywords: list[str] | None = None,
        max_pages_per_keyword: int = 2,
    ) -> int:
        """执行爬取。"""
        keywords = keywords or self.fetch_keywords()
        seen_ids: set[int] = set()
        start_count = len(store)

        for keyword in keywords:
            if len(store) >= max_recipes:
                break
            logger.info("豆果搜索关键词: %s", keyword)
            try:
                ids = self.search_recipe_ids(keyword, max_pages=max_pages_per_keyword)
            except Exception as exc:
                logger.warning("搜索失败 %s: %s", keyword, exc)
                continue

            for rid in ids:
                if len(store) >= max_recipes:
                    break
                self._collect_one(store, seen_ids, rid, max_recipes)

        # 关键词不够时，通过相关菜谱链接 BFS 补充
        if len(store) < max_recipes:
            bfs_queue: list[int] = []
            for rid in list(seen_ids)[:200]:
                try:
                    bfs_queue.extend(self.discover_related_ids(rid))
                except Exception:
                    pass
            bfs_queue = [x for x in bfs_queue if x not in seen_ids]

            while bfs_queue and len(store) < max_recipes:
                rid = bfs_queue.pop(0)
                if rid in seen_ids:
                    continue
                if self._collect_one(store, seen_ids, rid, max_recipes):
                    try:
                        for related in self.discover_related_ids(rid):
                            if related not in seen_ids and related not in bfs_queue:
                                bfs_queue.append(related)
                    except Exception:
                        pass

        store.save()
        return len(store) - start_count

    def _collect_one(
        self,
        store: JsonRecipeStore,
        seen_ids: set[int],
        rid: int,
        max_recipes: int,
    ) -> bool:
        if len(store) >= max_recipes or rid in seen_ids:
            return False
        seen_ids.add(rid)
        try:
            raw = self.fetch_detail(rid)
            if not raw:
                return False
            recipe = self.parse_recipe(rid, raw)
            if recipe and store.add(recipe):
                logger.info("已采集 [%d/%d] %s", len(store), max_recipes, recipe.title)
                if len(store) % 20 == 0:
                    store.save()
                sleep_interval(self.delay)
                return True
        except Exception as exc:
            logger.warning("详情失败 id=%s: %s", rid, exc)
        return False


def _parse_servings(value: Any) -> int | None:
    if value is None:
        return None
    m = re.search(r"(\d+)", str(value))
    return int(m.group(1)) if m else None
