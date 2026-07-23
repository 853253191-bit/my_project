# -*- coding: utf-8 -*-
"""数据库模型与建表 SQL。"""

from __future__ import annotations

CREATE_RECIPES_TABLE = """
CREATE TABLE IF NOT EXISTS recipes (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    description   TEXT,
    cuisine       TEXT,
    difficulty    TEXT,
    cook_minutes  INTEGER,
    servings      INTEGER,
    mood_tags     TEXT,
    taste_tags    TEXT,
    health_tags   TEXT,
    weather_tags  TEXT,
    ingredients   TEXT NOT NULL,
    steps         TEXT NOT NULL,
    nutrition     TEXT,
    source_url    TEXT,
    source_site   TEXT,
    image_url     TEXT,
    created_at    TEXT,
    updated_at    TEXT
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_recipes_cuisine ON recipes(cuisine);",
    "CREATE INDEX IF NOT EXISTS idx_recipes_cook_minutes ON recipes(cook_minutes);",
]
