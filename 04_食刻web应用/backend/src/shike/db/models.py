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

# 用户推荐反馈（recipe_id 与 recipes.id 一致，使用 TEXT）
CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_id TEXT,
    recipe_id TEXT,
    query_text TEXT,
    filters TEXT,
    rating TEXT,
    comment TEXT,
    client_ip TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_FEEDBACK_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_feedback_recipe_id ON feedback(recipe_id);",
    "CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);",
    "CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);",
]
