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

# 用户账户（recipe 外键用 TEXT id）
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    preferences TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_USERS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
]

CREATE_FAVORITES_TABLE = """
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    recipe_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, recipe_id)
);
"""

CREATE_FAVORITES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_favorites_recipe_id ON favorites(recipe_id);",
]

CREATE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    recipe_id TEXT NOT NULL,
    query_text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_HISTORY_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_history_user_id ON history(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at);",
]
