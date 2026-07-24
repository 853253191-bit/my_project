# -*- coding: utf-8 -*-
"""SQLite 食谱仓储。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from shike.db.models import (
    CREATE_FEEDBACK_INDEXES,
    CREATE_FEEDBACK_TABLE,
    CREATE_INDEXES,
    CREATE_RECIPES_TABLE,
)

# 前端辣度 0~3 → 允许的 spicy_level 上限（生成列 0~5）
SPICE_LEVEL_MAX = {0: 0, 1: 2, 2: 3, 3: 5}

# 健康目标 → diet_labels_str 关键词（OR 匹配）
HEALTH_GOAL_TO_DIET = {
    "减脂": ["低卡", "少油"],
    "增肌": ["高蛋白"],
    "控糖": ["低卡", "控糖"],
    "素食": ["纯素食", "素食"],
}


class RecipeRepository:
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
            conn.execute(CREATE_RECIPES_TABLE)
            for stmt in CREATE_INDEXES:
                conn.execute(stmt)
            conn.execute(CREATE_FEEDBACK_TABLE)
            for stmt in CREATE_FEEDBACK_INDEXES:
                conn.execute(stmt)
            conn.commit()

    def save_feedback(
        self,
        *,
        recipe_id: str,
        rating: str,
        session_id: str | None = None,
        user_id: str | None = None,
        query_text: str | None = None,
        filters: dict[str, Any] | None = None,
        comment: str | None = None,
        client_ip: str | None = None,
    ) -> int:
        """写入推荐反馈，返回新行 id。"""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO feedback (
                    session_id, user_id, recipe_id, query_text,
                    filters, rating, comment, client_ip
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    recipe_id,
                    query_text,
                    json.dumps(filters or {}, ensure_ascii=False),
                    rating,
                    comment,
                    client_ip,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _recipe_to_row(self, recipe: dict[str, Any]) -> dict[str, Any]:
        rid = recipe.get("id") or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": rid,
            "title": recipe["title"],
            "description": recipe.get("description", ""),
            "cuisine": recipe.get("cuisine", ""),
            "difficulty": recipe.get("difficulty", ""),
            "cook_minutes": recipe.get("cook_minutes"),
            "servings": recipe.get("servings"),
            "mood_tags": json.dumps(recipe.get("mood_tags", []), ensure_ascii=False),
            "taste_tags": json.dumps(recipe.get("taste_tags", []), ensure_ascii=False),
            "health_tags": json.dumps(recipe.get("health_tags", []), ensure_ascii=False),
            "weather_tags": json.dumps(recipe.get("weather_tags", []), ensure_ascii=False),
            "ingredients": json.dumps(recipe.get("ingredients", []), ensure_ascii=False),
            "steps": json.dumps(recipe.get("steps", []), ensure_ascii=False),
            "nutrition": json.dumps(recipe.get("nutrition", {}), ensure_ascii=False),
            "source_url": recipe.get("source_url", ""),
            "source_site": recipe.get("source_site", ""),
            "image_url": recipe.get("image_url", ""),
            "created_at": recipe.get("created_at", now),
            "updated_at": now,
        }

    def _execute_upsert(self, conn: sqlite3.Connection, row: dict[str, Any]) -> None:
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        updates = ", ".join(f"{k}=excluded.{k}" for k in row if k != "id")
        sql = (
            f"INSERT INTO recipes ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}"
        )
        conn.execute(sql, list(row.values()))

    def upsert(self, recipe: dict[str, Any]) -> str:
        row = self._recipe_to_row(recipe)
        with self._connect() as conn:
            self._execute_upsert(conn, row)
            conn.commit()
        return row["id"]

    def upsert_many(self, recipes: list[dict[str, Any]]) -> int:
        with self._connect() as conn:
            for recipe in recipes:
                self._execute_upsert(conn, self._recipe_to_row(recipe))
            conn.commit()
        return len(recipes)

    def get_by_id(self, recipe_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]

    def list_all(self, limit: int = 10000) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM recipes LIMIT ?", (limit,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def filter_by_tags(
        self,
        mood: str | None = None,
        taste: list[str] | None = None,
        health_goal: str | None = None,
        max_cook_minutes: int | None = None,
        spice_level: int | None = None,
        max_greasiness: int | None = None,
        ai_difficulty: str | None = None,
        cuisine: str | None = None,
        exclude_allergens: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """按标签与 ai_tags 平铺列筛选。

        保留原有 mood_tags / taste_tags / health_tags / cook_minutes 逻辑，
        并叠加 greasiness / spicy_level / estimated_time 等生成列条件。
        """
        clauses: list[str] = []
        params: list[Any] = []

        # ---- 原有标签字段过滤（保留）----
        if mood:
            clauses.append("mood_tags LIKE ?")
            params.append(f"%{mood}%")
        if taste:
            for t in taste:
                clauses.append("taste_tags LIKE ?")
                params.append(f"%{t}%")
        if health_goal and health_goal != "无":
            # 原 health_tags + 新 diet_labels_str（OR）
            diet_keys = HEALTH_GOAL_TO_DIET.get(health_goal, [health_goal])
            health_parts = ["health_tags LIKE ?"]
            health_params: list[Any] = [f"%{health_goal}%"]
            for key in diet_keys:
                health_parts.append("diet_labels_str LIKE ?")
                health_params.append(f"%{key}%")
            clauses.append(f"({' OR '.join(health_parts)})")
            params.extend(health_params)

        # ---- 生成列：烹饪时长（优先 estimated_time，回退 cook_minutes）----
        if max_cook_minutes:
            clauses.append(
                "("
                "(estimated_time IS NOT NULL AND estimated_time <= ?) "
                "OR (estimated_time IS NULL AND (cook_minutes IS NULL OR cook_minutes <= ?))"
                ")"
            )
            params.extend([max_cook_minutes, max_cook_minutes])

        # ---- 生成列：辣度 ----
        if spice_level is not None and spice_level in SPICE_LEVEL_MAX:
            max_spicy = SPICE_LEVEL_MAX[spice_level]
            clauses.append("(spicy_level IS NULL OR spicy_level <= ?)")
            params.append(max_spicy)

        # ---- 生成列：油腻度 ----
        if max_greasiness is not None:
            clauses.append("(greasiness IS NULL OR greasiness <= ?)")
            params.append(max_greasiness)

        # ---- 生成列：AI 难度 ----
        if ai_difficulty:
            clauses.append("(ai_difficulty IS NULL OR ai_difficulty = ?)")
            params.append(ai_difficulty)

        # ---- 生成列：主菜系 ----
        if cuisine:
            clauses.append("(cuisine_main = ? OR cuisine LIKE ?)")
            params.extend([cuisine, f"%{cuisine}%"])

        # ---- 生成列：排除过敏原 ----
        if exclude_allergens:
            for allergen in exclude_allergens:
                a = allergen.strip()
                if not a:
                    continue
                clauses.append(
                    "(allergens_str IS NULL OR allergens_str = '' OR allergens_str NOT LIKE ?)"
                )
                params.append(f"%{a}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM recipes {where} LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for key in ("mood_tags", "taste_tags", "health_tags", "weather_tags", "ingredients", "steps", "nutrition"):
            if d.get(key):
                d[key] = json.loads(d[key])
            else:
                d[key] = [] if key != "nutrition" else {}

        # 解析 ai_tags JSON；平铺列已由生成列提供，一并保留便于接口使用
        raw_ai = d.get("ai_tags")
        if isinstance(raw_ai, str) and raw_ai.strip():
            try:
                d["ai_tags"] = json.loads(raw_ai)
            except json.JSONDecodeError:
                d["ai_tags"] = None
        elif not raw_ai:
            d["ai_tags"] = None

        return d
