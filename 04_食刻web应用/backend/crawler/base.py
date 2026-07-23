# -*- coding: utf-8 -*-
"""爬虫公共工具：数据结构、JSON 存储、标签映射。"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class CrawlRecipe:
    title: str
    description: str = ""
    cuisine: str = "家常菜"
    difficulty: str = "简单"
    cook_minutes: int | None = 30
    servings: int | None = 2
    mood_tags: list[str] = field(default_factory=list)
    taste_tags: list[str] = field(default_factory=list)
    health_tags: list[str] = field(default_factory=list)
    weather_tags: list[str] = field(default_factory=list)
    ingredients: list[dict[str, str]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    nutrition: dict[str, Any] = field(default_factory=dict)
    source_url: str = ""
    source_site: str = ""
    image_url: str = ""
    tags: list[str] = field(default_factory=list)
    recipe_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["id"] = self.recipe_id or str(uuid4())
        data.pop("recipe_id", None)
        return data


class JsonRecipeStore:
    """增量写入 JSON 文件（支持多线程）。"""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[dict[str, Any]] = []
        self._keys: set[str] = set()
        self._lock = threading.Lock()
        if self.path.is_file():
            self._load_existing()

    def _load_existing(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("recipes", [])
        for item in raw:
            key = self._dedup_key(item)
            if key not in self._keys:
                self._keys.add(key)
                self._items.append(item)

    @staticmethod
    def _dedup_key(item: dict[str, Any]) -> str:
        title = re.sub(r"\s+", "", item.get("title", ""))
        names = sorted(i.get("name", "") for i in item.get("ingredients", []))
        return f"{title}|{'|'.join(names)}|{item.get('source_url', '')}"

    def add(self, recipe: CrawlRecipe) -> bool:
        data = recipe.to_dict()
        key = self._dedup_key(data)
        with self._lock:
            if key in self._keys:
                return False
            self._keys.add(key)
            self._items.append(data)
            return True

    def save(self) -> int:
        with self._lock:
            payload = {"recipes": list(self._items), "count": len(self._items)}
            count = len(self._items)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return count

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


def sleep_interval(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def parse_amount_unit(note: str) -> tuple[str, str]:
    """解析用量字符串，如 250g、适量、2个。"""
    note = note.strip()
    if not note:
        return "", ""
    m = re.match(r"^([\d./]+)\s*([a-zA-Z\u4e00-\u9fff]+)$", note)
    if m:
        return m.group(1), m.group(2)
    return note, ""


def map_tags(raw_tags: list[str], title: str = "", description: str = "") -> dict[str, list[str]]:
    """将站点标签映射到项目标签体系。"""
    text = " ".join(raw_tags + [title, description])
    taste_tags: list[str] = []
    health_tags: list[str] = []
    weather_tags: list[str] = []
    mood_tags: list[str] = []

    taste_rules = {
        "麻辣": ["麻辣", "辣", "川菜", "湘菜"],
        "酸甜": ["酸甜", "糖醋", "番茄"],
        "清淡": ["清淡", "蒸", "白灼", "养生"],
        "咸鲜": ["咸鲜", "家常", "红烧", "焖"],
    }
    health_rules = {
        "减脂": ["减脂", "低脂", "轻食", "沙拉"],
        "控糖": ["控糖", "无糖"],
        "素食": ["素食", "素菜", "全素"],
        "高蛋白": ["高蛋白", "健身", "增肌"],
    }
    weather_rules = {
        "夏季": ["夏季", "夏天", "清凉", "解暑"],
        "冬季": ["冬季", "冬天", "暖胃", "进补"],
        "雨天适宜": ["雨天", "暖汤", "汤羹"],
    }
    mood_rules = {
        "想治愈": ["治愈", "暖心", "温馨"],
        "想尝鲜": ["尝鲜", "创意", "新派"],
        "疲惫": ["快手", "简单", "省事"],
        "开心": ["宴客", "聚餐", "节日"],
    }

    for tag, keywords in taste_rules.items():
        if any(k in text for k in keywords):
            taste_tags.append(tag)
    for tag, keywords in health_rules.items():
        if any(k in text for k in keywords):
            health_tags.append(tag)
    for tag, keywords in weather_rules.items():
        if any(k in text for k in keywords):
            weather_tags.append(tag)
    for tag, keywords in mood_rules.items():
        if any(k in text for k in keywords):
            mood_tags.append(tag)

    return {
        "taste_tags": taste_tags or ["咸鲜"],
        "health_tags": health_tags,
        "weather_tags": weather_tags,
        "mood_tags": mood_tags,
    }


def parse_minutes(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)\s*分钟", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*小时", text)
    if m:
        return int(m.group(1)) * 60
    if "小时" in text:
        return 60
    return None
