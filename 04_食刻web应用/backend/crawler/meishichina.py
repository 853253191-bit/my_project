# -*- coding: utf-8 -*-
"""美食天下爬虫（分类分页列表 + 多 worker 并行详情）。"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.base import (
    CrawlRecipe,
    JsonRecipeStore,
    map_tags,
    parse_amount_unit,
    sleep_interval,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.meishichina.com"
HOME_URL = "https://home.meishichina.com"
TYPE_INDEX_URL = "https://home.meishichina.com/recipe-type.html"

# 备用专题页（分类采集失败时补充）
DEFAULT_TOPICS = [
    "/mofang/hongshaorou/",
    "/mofang/gongbaojiding/",
    "/mofang/mapodoufu/",
    "/mofang/tangculiji/",
    "/mofang/koushuiji/",
    "/mofang/xihongshijidan/",
    "/mofang/jiaozi/",
    "/mofang/baozi/",
    "/mofang/miantiao/",
    "/mofang/haixian/",
    "/mofang/suancaiyu/",
    "/mofang/shuizhuyu/",
]


def _launch_browser(headless: bool, browser_channel: str):
    """每个线程独立启动 Playwright 浏览器。"""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    launch_kwargs: dict[str, Any] = {"headless": headless}
    if browser_channel:
        launch_kwargs["channel"] = browser_channel
    browser = pw.chromium.launch(**launch_kwargs)
    context = browser.new_context(
        user_agent=USER_AGENT,
        locale="zh-CN",
        viewport={"width": 1280, "height": 800},
    )
    page = context.new_page()
    return pw, browser, page


def _fetch_html_on_page(page: Any, url: str, delay: float, wait_selector: str | None = None) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=30000)
        except Exception:
            logger.warning("等待选择器超时: %s", wait_selector)
    sleep_interval(delay)
    return page.content()


def _extract_recipe_urls(html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for href in re.findall(r'https?://home\.meishichina\.com/recipe-\d+\.html', html):
        if href not in seen:
            seen.add(href)
            urls.append(href)
    for rid in re.findall(r'recipe-(\d+)\.html', html):
        full = f"{HOME_URL}/recipe-{rid}.html"
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


class MeishichinaCrawler:
    def __init__(
        self,
        delay: float = 1.5,
        headless: bool = False,
        browser_channel: str = "msedge",
        workers: int = 3,
        max_pages_per_category: int = 30,
    ):
        self.delay = delay
        self.headless = headless
        self.browser_channel = browser_channel
        self.workers = max(1, min(workers, 10))
        self.max_pages_per_category = max(1, max_pages_per_category)
        self._playwright = None
        self._browser = None
        self._page = None

    def _ensure_browser(self) -> None:
        if self._page is not None:
            return
        self._playwright, self._browser, self._page = _launch_browser(
            self.headless, self.browser_channel
        )

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None

    def fetch_html(self, url: str, wait_selector: str | None = None) -> str:
        self._ensure_browser()
        assert self._page is not None
        return _fetch_html_on_page(self._page, url, self.delay, wait_selector)

    def fetch_categories(self) -> list[str]:
        """从菜谱分类总页提取分类链接。"""
        logger.info("拉取分类目录: %s", TYPE_INDEX_URL)
        html = self.fetch_html(TYPE_INDEX_URL, wait_selector="a[href*='/recipe/']")
        cats: list[str] = []
        seen: set[str] = set()
        for href in re.findall(r'https?://home\.meishichina\.com/recipe/[a-z0-9\-]+/?', html):
            # 排除分页与无关路径
            if "/page/" in href:
                continue
            path = href.rstrip("/") + "/"
            if path not in seen:
                seen.add(path)
                cats.append(path)
        # 相对路径
        for m in re.findall(r'href="(/recipe/[a-z0-9\-]+/?)"', html):
            if "/page/" in m:
                continue
            full = urljoin(HOME_URL, m).rstrip("/") + "/"
            if full not in seen:
                seen.add(full)
                cats.append(full)
        logger.info("共发现 %d 个分类", len(cats))
        return cats

    def collect_recipe_urls(
        self,
        topics: list[str] | None = None,
        limit: int = 5000,
        use_categories: bool = True,
        urls_save_path: Path | None = None,
    ) -> list[str]:
        """分类列表（默认只取首页，不深翻页）+ 专题页，收集详情链接。"""
        urls: list[str] = []
        seen: set[str] = set()

        def _persist() -> None:
            if urls_save_path:
                urls_save_path.parent.mkdir(parents=True, exist_ok=True)
                urls_save_path.write_text(
                    json.dumps({"urls": urls, "count": len(urls)}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        def _add_from_html(html: str) -> int:
            found = 0
            for full in _extract_recipe_urls(html):
                if full not in seen:
                    seen.add(full)
                    urls.append(full)
                    found += 1
            return found

        if use_categories:
            try:
                categories = self.fetch_categories()
            except Exception as exc:
                logger.warning("分类目录失败，回退专题页: %s", exc)
                categories = []

            for cat_url in categories:
                if len(urls) >= limit:
                    break
                # 每个分类只爬前 max_pages_per_category 页（可设为 1 跳过深翻）
                empty_pages = 0
                for page_no in range(1, self.max_pages_per_category + 1):
                    if len(urls) >= limit:
                        break
                    list_url = (
                        cat_url if page_no == 1 else f"{cat_url.rstrip('/')}/page/{page_no}/"
                    )
                    logger.info("分类列表: %s", list_url)
                    try:
                        html = self.fetch_html(list_url, wait_selector="a[href*='recipe-']")
                    except Exception as exc:
                        logger.warning("列表页失败 %s: %s", list_url, exc)
                        empty_pages += 1
                        if empty_pages >= 2:
                            break
                        continue
                    found = _add_from_html(html)
                    logger.info("  本页新增 %d，累计 %d", found, len(urls))
                    if found == 0:
                        empty_pages += 1
                        if empty_pages >= 2:
                            break
                    else:
                        empty_pages = 0
                _persist()

        topics = topics if topics is not None else DEFAULT_TOPICS
        for topic in topics:
            if len(urls) >= limit:
                break
            list_url = urljoin(BASE_URL, topic)
            logger.info("专题列表: %s", list_url)
            try:
                html = self.fetch_html(list_url, wait_selector="a[href*='recipe-']")
            except Exception as exc:
                logger.warning("专题页失败 %s: %s", list_url, exc)
                continue
            found = _add_from_html(html)
            logger.info("  专题新增 %d，累计 %d", found, len(urls))
        _persist()
        return urls

    @staticmethod
    def load_urls(path: Path) -> list[str]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return list(data.get("urls", []))
        return list(data) if isinstance(data, list) else []

    def crawl_details(
        self,
        store: JsonRecipeStore,
        urls: list[str],
        max_recipes: int = 100,
    ) -> int:
        """直接按 URL 列表抓详情（跳过翻页）。"""
        start_count = len(store)
        if not urls:
            return 0
        logger.info("美食天下直接抓详情：%d 个链接，workers=%d", len(urls), self.workers)
        chunks: list[list[str]] = [[] for _ in range(self.workers)]
        for i, url in enumerate(urls):
            chunks[i % self.workers].append(url)
        chunks = [c for c in chunks if c]
        with ThreadPoolExecutor(max_workers=len(chunks)) as pool:
            futures = [
                pool.submit(self._worker_crawl, i + 1, chunk, store, max_recipes)
                for i, chunk in enumerate(chunks)
            ]
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as exc:
                    logger.error("worker 任务失败: %s", exc)
        store.save()
        return len(store) - start_count

    def parse_detail(self, url: str, html: str) -> CrawlRecipe | None:
        soup = BeautifulSoup(html, "html.parser")
        title_el = soup.select_one("h1.title a, h1.title")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        m = re.search(r"recipe-(\d+)\.html", url)
        recipe_id = f"meishi_{m.group(1)}" if m else f"meishi_{abs(hash(url))}"

        desc_el = soup.select_one("#block_txt1, .recipemessage, meta[name='description']")
        if desc_el and desc_el.name == "meta":
            description = desc_el.get("content", "").strip()
        else:
            description = desc_el.get_text(strip=True) if desc_el else ""
        description = description.replace("\u201c", "").replace("\u201d", "").strip(" \"")

        img_el = soup.select_one(".recipephoto img, .recipDetail .cover img")
        image_url = ""
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src") or ""

        ingredients: list[dict[str, str]] = []
        for li in soup.select("fieldset.particulars li"):
            name_el = li.select_one(".category_s1 b, .category_s1 a b")
            amount_el = li.select_one(".category_s2")
            name = name_el.get_text(strip=True) if name_el else ""
            note = amount_el.get_text(strip=True) if amount_el else ""
            amount, unit = parse_amount_unit(note)
            if name:
                ingredients.append({"name": name, "amount": amount, "unit": unit})

        steps: list[dict[str, Any]] = []
        for li in soup.select(".recipeStep li"):
            word = li.select_one(".recipeStep_word")
            img = li.select_one(".recipeStep_img img")
            text = word.get_text(strip=True) if word else li.get_text(strip=True)
            text = re.sub(r"^\d+\s*", "", text)
            if not text:
                continue
            step_img = ""
            if img:
                step_img = img.get("data-src") or img.get("src") or ""
            steps.append({
                "order": len(steps) + 1,
                "text": text,
                "image_url": step_img,
            })

        if len(ingredients) < 2 or len(steps) < 2:
            return None

        raw_tags: list[str] = []
        for a in soup.select("#path a.vest, .recipeCategory_sub_R a, .recipeCategory_sub a"):
            tag = a.get_text(strip=True)
            if tag and tag not in raw_tags:
                raw_tags.append(tag)

        tag_map = map_tags(raw_tags, title, description)
        cuisine = raw_tags[0] if raw_tags else "家常菜"

        return CrawlRecipe(
            recipe_id=recipe_id,
            title=title,
            description=description,
            cuisine=cuisine,
            difficulty="简单",
            mood_tags=tag_map["mood_tags"],
            taste_tags=tag_map["taste_tags"],
            health_tags=tag_map["health_tags"],
            weather_tags=tag_map["weather_tags"],
            ingredients=ingredients,
            steps=steps,
            source_url=url,
            source_site="meishichina",
            image_url=image_url,
            tags=raw_tags,
        )

    def _worker_crawl(
        self,
        worker_id: int,
        urls: list[str],
        store: JsonRecipeStore,
        max_recipes: int,
    ) -> int:
        """单个 worker：独立浏览器，串行处理分配到的 URL。"""
        added = 0
        pw = browser = page = None
        try:
            pw, browser, page = _launch_browser(self.headless, self.browser_channel)
            logger.info("美食天下 worker-%d 启动，分配 %d 条链接", worker_id, len(urls))
            for url in urls:
                if len(store) >= max_recipes:
                    break
                try:
                    html = _fetch_html_on_page(
                        page, url, self.delay, wait_selector="h1.title a, .recipeStep"
                    )
                    recipe = self.parse_detail(url, html)
                    if recipe and store.add(recipe):
                        added += 1
                        logger.info(
                            "已采集 [%d/%d] (w%d) %s",
                            len(store),
                            max_recipes,
                            worker_id,
                            recipe.title,
                        )
                        if len(store) % 10 == 0:
                            store.save()
                except Exception as exc:
                    logger.warning("详情失败 (w%d) %s: %s", worker_id, url, exc)
        except Exception as exc:
            logger.error("worker-%d 异常: %s", worker_id, exc)
        finally:
            if browser:
                browser.close()
            if pw:
                pw.stop()
        return added

    def crawl(
        self,
        store: JsonRecipeStore,
        max_recipes: int = 100,
        topics: list[str] | None = None,
        urls_file: Path | None = None,
        from_urls: Path | None = None,
    ) -> int:
        start_count = len(store)
        try:
            if from_urls and from_urls.is_file():
                urls = self.load_urls(from_urls)
                logger.info("从文件加载 %d 个链接: %s", len(urls), from_urls)
            else:
                urls_save = urls_file or Path("data/raw/meishichina_urls.json")
                urls = self.collect_recipe_urls(
                    topics=topics,
                    limit=max(max_recipes * 2, 500),
                    use_categories=True,
                    urls_save_path=urls_save,
                )
                self.close()
            if not urls:
                return 0
            return self.crawl_details(store, urls, max_recipes=max_recipes)
        finally:
            store.save()
            self.close()