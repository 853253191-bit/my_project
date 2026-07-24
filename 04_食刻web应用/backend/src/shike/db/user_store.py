# -*- coding: utf-8 -*-
"""用户 / 收藏 / 历史 SQLite 仓储。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from shike.db.models import (
    CREATE_FAVORITES_INDEXES,
    CREATE_FAVORITES_TABLE,
    CREATE_HISTORY_INDEXES,
    CREATE_HISTORY_TABLE,
    CREATE_USERS_INDEXES,
    CREATE_USERS_TABLE,
)


def _ingredient_names(ingredients: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(ingredients, list):
        return names
    for item in ingredients:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("ingredient") or "").strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


class UserStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_USERS_TABLE)
            for stmt in CREATE_USERS_INDEXES:
                conn.execute(stmt)
            conn.execute(CREATE_FAVORITES_TABLE)
            for stmt in CREATE_FAVORITES_INDEXES:
                conn.execute(stmt)
            conn.execute(CREATE_HISTORY_TABLE)
            for stmt in CREATE_HISTORY_INDEXES:
                conn.execute(stmt)
            conn.commit()

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
        prefs_raw = row["preferences"] if "preferences" in row.keys() else "{}"
        try:
            preferences = json.loads(prefs_raw or "{}")
        except json.JSONDecodeError:
            preferences = {}
        if not isinstance(preferences, dict):
            preferences = {}
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "email": row["email"],
            "hashed_password": row["hashed_password"],
            "is_active": bool(row["is_active"]),
            "preferences": preferences,
            "created_at": row["created_at"] if "created_at" in row.keys() else None,
        }

    def create_user(
        self, *, username: str, email: str, hashed_password: str
    ) -> dict[str, Any]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, email, hashed_password, preferences)
                VALUES (?, ?, ?, ?)
                """,
                (username, email, hashed_password, "{}"),
            )
            conn.commit()
            uid = int(cur.lastrowid)
        user = self.get_by_id(uid)
        assert user is not None
        return user

    def get_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def update_preferences(
        self, user_id: int, preferences: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET preferences = ? WHERE id = ?",
                (json.dumps(preferences or {}, ensure_ascii=False), user_id),
            )
            conn.commit()
        return self.get_by_id(user_id)

    # ---------- favorites ----------
    def add_favorite(self, user_id: int, recipe_id: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO favorites (user_id, recipe_id)
                VALUES (?, ?)
                """,
                (user_id, recipe_id),
            )
            conn.commit()
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = conn.execute(
                "SELECT id FROM favorites WHERE user_id = ? AND recipe_id = ?",
                (user_id, recipe_id),
            ).fetchone()
            return int(row["id"]) if row else 0

    def remove_favorite(self, user_id: int, recipe_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM favorites WHERE user_id = ? AND recipe_id = ?",
                (user_id, recipe_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def is_favorited(self, user_id: int, recipe_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM favorites WHERE user_id = ? AND recipe_id = ? LIMIT 1",
                (user_id, recipe_id),
            ).fetchone()
        return row is not None

    def list_favorite_ids(self, user_id: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT recipe_id FROM favorites WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [str(r["recipe_id"]) for r in rows]

    def list_favorites(
        self, user_id: int, *, page: int = 1, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        page = max(page, 1)
        limit = max(min(limit, 100), 1)
        offset = (page - 1) * limit
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM favorites WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
            rows = conn.execute(
                """
                SELECT f.id AS favorite_id, f.recipe_id, f.created_at,
                       r.title, r.decision_summary, r.cuisine_main,
                       r.estimated_time, r.image_url, r.ingredients
                FROM favorites f
                LEFT JOIN recipes r ON r.id = f.recipe_id
                WHERE f.user_id = ?
                ORDER BY f.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            ingredients = []
            if row["ingredients"]:
                try:
                    ingredients = _ingredient_names(json.loads(row["ingredients"]))
                except Exception:  # noqa: BLE001
                    ingredients = []
            items.append({
                "favorite_id": int(row["favorite_id"]),
                "recipe_id": str(row["recipe_id"]),
                "created_at": row["created_at"],
                "title": row["title"],
                "decision_summary": row["decision_summary"],
                "cuisine_main": row["cuisine_main"],
                "estimated_time": row["estimated_time"],
                "image_url": row["image_url"],
                "ingredients": ingredients,
            })
        return items, int(total)

    # ---------- history ----------
    def add_history(
        self, user_id: int, recipe_id: str, query_text: str | None = None
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO history (user_id, recipe_id, query_text)
                VALUES (?, ?, ?)
                """,
                (user_id, recipe_id, query_text),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_history(
        self, user_id: int, *, page: int = 1, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        page = max(page, 1)
        limit = max(min(limit, 100), 1)
        offset = (page - 1) * limit
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM history WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
            rows = conn.execute(
                """
                SELECT h.id AS history_id, h.recipe_id, h.query_text, h.created_at,
                       r.title, r.decision_summary, r.cuisine_main,
                       r.estimated_time, r.image_url, r.ingredients
                FROM history h
                LEFT JOIN recipes r ON r.id = h.recipe_id
                WHERE h.user_id = ?
                ORDER BY h.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            ingredients = []
            if row["ingredients"]:
                try:
                    ingredients = _ingredient_names(json.loads(row["ingredients"]))
                except Exception:  # noqa: BLE001
                    ingredients = []
            items.append({
                "history_id": int(row["history_id"]),
                "recipe_id": str(row["recipe_id"]),
                "query_text": row["query_text"],
                "created_at": row["created_at"],
                "title": row["title"],
                "decision_summary": row["decision_summary"],
                "cuisine_main": row["cuisine_main"],
                "estimated_time": row["estimated_time"],
                "image_url": row["image_url"],
                "ingredients": ingredients,
            })
        return items, int(total)

    def clear_history(self, user_id: int) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM history WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            return int(cur.rowcount)
