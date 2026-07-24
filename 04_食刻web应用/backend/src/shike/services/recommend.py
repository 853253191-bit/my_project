# -*- coding: utf-8 -*-
"""混合推荐服务：动态扩召回 + 偏好加权 + 推荐理由。"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any

from shike.config import AppConfig
from shike.db.repository import RecipeRepository
from shike.rag.vector_store import RecipeVectorStore
from shike.services.title_dedupe import dedupe_recipe_items

logger = logging.getLogger(__name__)


def _ingredient_names(ingredients: Any) -> list[str]:
    """从食材列表提取名称（兼容 str / {name: ...}）。"""
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


def generate_reason(query_text: str, decision_summary: str | None = None) -> str:
    """根据用户输入关键词生成推荐理由变体（规则映射，不调 LLM）。"""
    q = query_text or ""
    default = (decision_summary or "").strip() or "这道菜和你现在的状态挺合拍，不妨试试"

    rules: list[tuple[list[str], str]] = [
        (["累", "疲惫", "加班", "辛苦", "困"], "工作一天辛苦了，这道菜能让你快速回血"),
        (["开心", "庆祝", "高兴", "爽"], "生活需要一点仪式感，试试这道菜吧"),
        (["尝鲜", "新鲜", "不一样", "换换"], "今天来点不一样的，看看这道菜合不合你胃口"),
        (["减肥", "减脂", "低卡", "瘦"], "低卡又满足，吃这道菜不会有负担"),
        (["下雨", "降温", "冷", "冬天", "暖"], "冷冷的天气和热腾腾的饭菜最配了"),
    ]
    for keys, reason in rules:
        if any(k in q for k in keys):
            return reason
    return default


def _apply_one_relax(
    filters: dict[str, Any], kind: str
) -> tuple[dict[str, Any], str]:
    """对 filters 应用一种放宽；无可放宽时返回空描述。"""
    f = deepcopy(filters)
    if kind == "greasiness" and f.get("greasiness_max") is not None:
        old = int(f["greasiness_max"])
        f["greasiness_max"] = old + 1
        return f, f"greasiness_max {old}->{f['greasiness_max']}"
    if kind == "time" and f.get("estimated_time_max") is not None:
        old = int(f["estimated_time_max"])
        f["estimated_time_max"] = old + 15
        return f, f"estimated_time_max {old}->{f['estimated_time_max']}"
    if kind == "spicy" and f.get("spicy_level_max") is not None:
        old = int(f["spicy_level_max"])
        f["spicy_level_max"] = old + 1
        return f, f"spicy_level_max {old}->{f['spicy_level_max']}"
    if kind == "cuisine" and f.get("cuisine_main"):
        old = f.pop("cuisine_main", None)
        return f, f"去掉 cuisine_main={old}"
    return f, ""


def _has_hard_filters(filters: dict[str, Any] | None) -> bool:
    if not filters:
        return False
    keys = (
        "greasiness_max",
        "spicy_level_max",
        "estimated_time_max",
        "cuisine_main",
        "ai_difficulty",
        "exclude_allergens",
        "include_diet_labels",
    )
    return any(filters.get(k) not in (None, "", []) for k in keys)


def merge_user_preferences(
    filters: dict[str, Any] | None,
    preferences: dict[str, Any] | None,
) -> dict[str, Any]:
    """将用户偏好合并进本次 filters（请求中已显式设置的字段优先）。"""
    out = dict(filters or {})
    prefs = preferences or {}
    if not prefs:
        return out

    for key in (
        "greasiness_max",
        "spicy_level_max",
        "estimated_time_max",
        "cuisine_main",
        "ai_difficulty",
    ):
        if out.get(key) in (None, "") and prefs.get(key) not in (None, ""):
            out[key] = prefs[key]

    # 过敏原：合并去重
    req_all = list(out.get("exclude_allergens") or [])
    pref_all = list(prefs.get("exclude_allergens") or [])
    merged_all: list[str] = []
    for a in req_all + pref_all:
        s = str(a).strip()
        if s and s not in merged_all:
            merged_all.append(s)
    if merged_all:
        out["exclude_allergens"] = merged_all

    if out.get("include_diet_labels") in (None, []) and prefs.get("include_diet_labels"):
        out["include_diet_labels"] = list(prefs["include_diet_labels"])

    return out


def apply_favorite_boost(
    items: list[dict[str, Any]],
    favorite_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """标记 is_favorited，并将收藏过的菜排到前面。"""
    fav_set = {str(x) for x in (favorite_ids or [])}
    for it in items:
        rid = str(it.get("id") or "")
        it["is_favorited"] = rid in fav_set
    if not fav_set:
        return items
    # 收藏优先，其次保持原相对顺序
    boosted = sorted(
        enumerate(items),
        key=lambda pair: (0 if pair[1].get("is_favorited") else 1, pair[0]),
    )
    return [it for _, it in boosted]


class HybridRecommender:
    def __init__(self, config: AppConfig, repo: RecipeRepository):
        self.config = config
        self.repo = repo
        self.store = RecipeVectorStore(config)

    def ensure_vector_db(self) -> None:
        """Chroma 未初始化时自动执行迁移。"""
        if self.store.is_ready():
            return
        logger.warning("Chroma 为空，开始自动迁移 ...")
        import sys
        from pathlib import Path

        from shike.config import resolve_path

        backend_root = Path(__file__).resolve().parents[3]
        if str(backend_root) not in sys.path:
            sys.path.insert(0, str(backend_root))
        from pipeline.migrate_to_vector_db import migrate

        db_path = resolve_path(
            os.getenv("DB_PATH", "") or self.config.data.sqlite_path
        )
        chroma_path = resolve_path(
            os.getenv("CHROMA_PATH", "") or self.config.rag.store_path
        )
        self.store.close()
        try:
            migrate(db_path=db_path, chroma_path=chroma_path, batch_size=50)
        finally:
            self.store = RecipeVectorStore(self.config)

    def _hit_to_item(self, hit: dict[str, Any], query_text: str = "") -> dict[str, Any]:
        rid = str(hit.get("recipe_id") or hit.get("_chroma_id") or "")
        recipe = self.repo.get_by_id(rid) if rid else None
        if recipe:
            summary = recipe.get("decision_summary") or (
                (recipe.get("ai_tags") or {}).get("decision_summary", "")
            )
            return {
                "id": recipe.get("id"),
                "title": recipe.get("title"),
                "decision_summary": summary,
                "reason": generate_reason(query_text, summary),
                "greasiness": recipe.get("greasiness"),
                "spicy_level": recipe.get("spicy_level"),
                "cuisine_main": recipe.get("cuisine_main"),
                "ai_difficulty": recipe.get("ai_difficulty"),
                "estimated_time": recipe.get("estimated_time"),
                "allergens_str": recipe.get("allergens_str"),
                "diet_labels_str": recipe.get("diet_labels_str"),
                "ai_tags": recipe.get("ai_tags"),
                "image_url": recipe.get("image_url"),
                "source_url": recipe.get("source_url"),
                "ingredients": _ingredient_names(recipe.get("ingredients")),
                "distance": hit.get("_distance"),
                "preference_score": hit.get("_preference_score"),
                "final_score": hit.get("_final_score"),
            }
        summary = ""
        return {
            "id": rid,
            "title": hit.get("title"),
            "decision_summary": summary,
            "reason": generate_reason(query_text, summary),
            "greasiness": hit.get("greasiness"),
            "spicy_level": hit.get("spicy_level"),
            "cuisine_main": hit.get("cuisine_main"),
            "ai_difficulty": hit.get("ai_difficulty"),
            "estimated_time": hit.get("estimated_time"),
            "allergens_str": hit.get("allergens_str"),
            "diet_labels_str": hit.get("diet_labels_str"),
            "ai_tags": None,
            "ingredients": [],
            "distance": hit.get("_distance"),
            "preference_score": hit.get("_preference_score"),
            "final_score": hit.get("_final_score"),
        }

    def _search_and_dedupe(
        self,
        query_text: str,
        filters: dict[str, Any] | None,
        top_k: int,
        use_preference: bool,
    ) -> list[dict[str, Any]]:
        fetch_k = max(top_k * 4, top_k)
        if use_preference and filters:
            hits = self.store.query_with_preference(
                query_text=query_text, filters=filters, top_k=fetch_k
            )
        else:
            hits = self.store.query(
                query_text=query_text, filters=filters, top_k=fetch_k
            )
        if not hits:
            return []
        raw_items = [self._hit_to_item(h, query_text) for h in hits]
        return dedupe_recipe_items(self.config, raw_items, keep=top_k, use_llm=True)

    def _random_fallback(self, query_text: str, limit: int = 3) -> list[dict[str, Any]]:
        """第 3 级兜底：全库随机。"""
        items: list[dict[str, Any]] = []
        with self.repo._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM recipes ORDER BY RANDOM() LIMIT ?",
                (limit,),
            ).fetchall()
        for row in rows:
            recipe = self.repo._row_to_dict(row)
            summary = recipe.get("decision_summary") or ""
            items.append({
                "id": recipe.get("id"),
                "title": recipe.get("title"),
                "decision_summary": summary,
                "reason": generate_reason(query_text, summary),
                "cuisine_main": recipe.get("cuisine_main"),
                "estimated_time": recipe.get("estimated_time"),
                "ai_difficulty": recipe.get("ai_difficulty"),
                "greasiness": recipe.get("greasiness"),
                "spicy_level": recipe.get("spicy_level"),
                "image_url": recipe.get("image_url"),
                "ingredients": _ingredient_names(recipe.get("ingredients")),
            })
        return items

    def recommend(
        self,
        query_text: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 3,
        favorite_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self.ensure_vector_db()
        filters = dict(filters or {})
        top_k = max(int(top_k or 3), 1)

        def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
            items = apply_favorite_boost(
                list(payload.get("items") or []), favorite_ids
            )
            payload["items"] = items
            payload["count"] = len(items)
            return payload

        # ----- 第 1 级：严格过滤 -----
        level1 = self._search_and_dedupe(
            query_text, filters, top_k, use_preference=bool(filters)
        )
        if len(level1) >= top_k:
            logger.info(
                "扩召回 level=1 | 严格过滤命中 %s 条，直接返回",
                len(level1),
            )
            return _finalize({
                "count": len(level1),
                "message": "",
                "items": level1,
                "recall_level": 1,
            })

        logger.info(
            "⚠️ 严格过滤仅 %s 条，开始放宽条件",
            len(level1),
        )

        # ----- 第 2 级：按优先级累计放宽（油腻→时间→辣度→菜系）-----
        level2: list[dict[str, Any]] = []
        relaxed = deepcopy(filters)
        applied: list[str] = []
        if _has_hard_filters(filters):
            for kind in ("greasiness", "time", "spicy", "cuisine"):
                relaxed, desc = _apply_one_relax(relaxed, kind)
                if not desc:
                    continue
                applied.append(desc)
                try:
                    found = self._search_and_dedupe(
                        query_text, relaxed, top_k, use_preference=True
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("扩召回第 2 级失败 kind=%s: %s", kind, exc)
                    continue
                logger.info(
                    "⚠️ 严格过滤仅 %s 条，放宽条件 %s 后找到 %s 条",
                    len(level1),
                    desc,
                    len(found),
                )
                if len(found) > len(level2):
                    level2 = found
                if len(level2) >= top_k:
                    break

        # 第 2 级凑满 top_k → 返回放宽结果
        if level2 and len(level2) >= top_k:
            msg = "为你适当放宽了筛选条件"
            logger.info("扩召回 level=2 | 返回 %s 条 | %s", len(level2), applied)
            return _finalize({
                "count": len(level2),
                "message": msg,
                "items": level2[:top_k],
                "recall_level": 2,
            })

        # 严格为 0、放宽后有结果 → 仍用第 2 级
        if not level1 and level2:
            msg = "为你适当放宽了筛选条件"
            logger.info("扩召回 level=2 | 严格为0，放宽后 %s 条", len(level2))
            return _finalize({
                "count": len(level2),
                "message": msg,
                "items": level2,
                "recall_level": 2,
            })

        # 放宽后仍不足：返回第 1 级（即使不足 top_k）
        if level1:
            logger.info(
                "扩召回 level=1(不足) | 放宽后仍不足 top_k，返回严格结果 %s 条",
                len(level1),
            )
            return _finalize({
                "count": len(level1),
                "message": "",
                "items": level1,
                "recall_level": 1,
            })

        # ----- 第 3 级：全库随机兜底 -----
        logger.info("⚠️ 所有过滤后为 0，启用随机兜底")
        items = self._random_fallback(query_text, limit=min(3, top_k))
        return _finalize({
            "count": len(items),
            "message": "当前条件太苛刻，先给你几道不错的菜开开胃",
            "items": items,
            "recall_level": 3,
        })

    def daily_recommendations(self, limit: int = 5) -> dict[str, Any]:
        """每日推荐：随机取样 + 菜名语义去重。"""
        fetch_n = max(limit * 4, limit)
        raw_items: list[dict[str, Any]] = []
        with self.repo._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM recipes ORDER BY RANDOM() LIMIT ?",
                (fetch_n,),
            ).fetchall()
        for row in rows:
            recipe = self.repo._row_to_dict(row)
            summary = recipe.get("decision_summary")
            raw_items.append({
                "id": recipe.get("id"),
                "title": recipe.get("title"),
                "decision_summary": summary,
                "reason": generate_reason("今日推荐", summary),
                "cuisine_main": recipe.get("cuisine_main"),
                "estimated_time": recipe.get("estimated_time"),
                "ai_difficulty": recipe.get("ai_difficulty"),
                "image_url": recipe.get("image_url"),
                "ingredients": _ingredient_names(recipe.get("ingredients")),
            })

        items = dedupe_recipe_items(
            self.config, raw_items, keep=limit, use_llm=True
        )
        return {"count": len(items), "items": items}
