# -*- coding: utf-8 -*-
"""豆果美食 HTML 详情页解析（API 返回 HTML 时的回退）。"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from crawler.base import parse_amount_unit


def parse_douguo_html(html: str, recipe_id: int, url: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(".title.text-lips, h1.title")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)
    intro_el = soup.select_one(".intro, .cookstory")
    description = intro_el.get_text(strip=True) if intro_el else ""

    img_el = soup.select_one("#banner img, .cover img, img.wb100")
    image_url = ""
    if img_el:
        image_url = (img_el.get("src") or "").strip()
    # 优先使用原图 data-origin（更高清）
    banner = soup.select_one("#banner")
    if banner and banner.get("data-origin"):
        image_url = str(banner.get("data-origin")).strip() or image_url
    if not image_url:
        caiku = soup.select_one("img[src*='upload/caiku']")
        if caiku:
            image_url = (caiku.get("src") or "").strip()

    ingredients: list[dict[str, str]] = []
    names = soup.select(".scname, .material .name")
    nums = soup.select(".scnum, .material .num")
    for name_el, num_el in zip(names, nums):
        name = name_el.get_text(strip=True)
        note = num_el.get_text(strip=True)
        amount, unit = parse_amount_unit(note)
        if name:
            ingredients.append({"name": name, "amount": amount, "unit": unit})

    steps: list[dict[str, Any]] = []
    step_blocks = soup.select(".step")
    if step_blocks:
        for i, block in enumerate(step_blocks, start=1):
            text_el = block.select_one(".stepinfo, .text")
            text = text_el.get_text(strip=True) if text_el else block.get_text(strip=True)
            img_el = block.select_one("img")
            img_url = img_el.get("src", "") if img_el else ""
            if text:
                steps.append({"order": i, "text": text, "image_url": img_url})
    else:
        for i, step_el in enumerate(soup.select(".stepinfo"), start=1):
            text = step_el.get_text(strip=True)
            if text:
                steps.append({"order": i, "text": text, "image_url": ""})

    if len(ingredients) < 2 or len(steps) < 2:
        return None

    raw_tags = [a.get_text(strip=True) for a in soup.select(".cates a, a.tag") if a.get_text(strip=True)]

    return {
        "title": title,
        "cookstory": description,
        "tips": "",
        "major": [{"title": i["name"], "note": f"{i['amount']}{i['unit']}".strip()} for i in ingredients[: len(ingredients) // 2 + 1]],
        "minor": [{"title": i["name"], "note": f"{i['amount']}{i['unit']}".strip()} for i in ingredients[len(ingredients) // 2 + 1 :]],
        "cookstep": [{"position": s["order"], "content": s["text"], "image": s.get("image_url", "")} for s in steps],
        "image": image_url,
        "recipe_tags": raw_tags,
        "cook_time": _extract_meta(soup, r"时间|耗时"),
        "cook_difficulty": _extract_meta(soup, r"难度"),
        "_source_url": url,
        "_recipe_id": recipe_id,
    }


def _extract_meta(soup: BeautifulSoup, pattern: str) -> str:
    for el in soup.select(".desc li, .metas li, .tip"):
        text = el.get_text(strip=True)
        if re.search(pattern, text):
            return text
    return ""
