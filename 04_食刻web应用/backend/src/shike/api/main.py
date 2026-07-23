# -*- coding: utf-8 -*-
"""FastAPI 入口。

混合检索说明：
- 向量检索字段：query_text → Embedding → Chroma document 相似度
- 硬过滤字段：filters → Chroma metadata（greasiness / spicy_level / cuisine_main /
  ai_difficulty / estimated_time）+ 过敏原/饮食标签二次过滤
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from shike.api.schemas import (
    DailyResponse,
    HealthResponse,
    IntentResponse,
    RecommendResponse,
    RecipeItem,
    SearchRecipesResponse,
)
from shike.config import load_config, resolve_path
from shike.db.repository import RecipeRepository
from shike.models.schemas import (
    ChatRequest,
    GenerateRequest,
    ParseIntentRequest,
    RecommendRequest,
    SessionMessage,
    SessionResponse,
    WeatherResponse,
)
from shike.services.generator import RecipeGenerator
from shike.services.intent import parse_user_intent
from shike.services.recommend import HybridRecommender, _ingredient_names
from shike.services.session import SessionManager
from shike.services.weather import WeatherService

APP_VERSION = "0.1.0"
_config = None
_repo: RecipeRepository | None = None
_generator: RecipeGenerator | None = None
_sessions: SessionManager | None = None
_weather: WeatherService | None = None
_recommender: HybridRecommender | None = None

# Swagger 分组顺序
OPENAPI_TAGS = [
    {"name": "推荐", "description": "混合检索 / 每日推荐 / 随机菜谱"},
    {"name": "意图解析", "description": "自然语言解析为筛选条件与表单"},
    {"name": "对话", "description": "SSE 流式生成与多轮对话"},
    {"name": "菜谱", "description": "SQLite 筛选与会话"},
    {"name": "辅助", "description": "健康检查与天气"},
]


def _get_generator() -> RecipeGenerator:
    if _generator is None:
        raise RuntimeError("应用未初始化")
    return _generator


def _get_sessions() -> SessionManager:
    if _sessions is None:
        raise RuntimeError("应用未初始化")
    return _sessions


def _get_repo() -> RecipeRepository:
    if _repo is None:
        raise RuntimeError("应用未初始化")
    return _repo


def _get_recommender() -> HybridRecommender:
    if _recommender is None:
        raise RuntimeError("应用未初始化")
    return _recommender


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config, _repo, _generator, _sessions, _weather, _recommender
    _config = load_config()
    db_path = resolve_path(_config.data.sqlite_path)
    _repo = RecipeRepository(db_path)
    _sessions = SessionManager(_config)
    _weather = WeatherService(_config)
    _generator = RecipeGenerator(_config, _repo, _sessions, _weather)
    _recommender = HybridRecommender(_config, _repo)
    yield


def create_app() -> FastAPI:
    cfg = load_config()
    app = FastAPI(
        title="食刻 Shike",
        version=APP_VERSION,
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["辅助"])
    async def health() -> dict[str, Any]:
        count = _repo.count() if _repo else 0
        chroma_n = 0
        try:
            if _recommender:
                chroma_n = _recommender.store.count()
        except Exception:  # noqa: BLE001
            chroma_n = 0
        return {
            "status": "ok",
            "version": APP_VERSION,
            "recipe_count": count,
            "chroma_count": chroma_n,
        }

    # ---------- 混合检索：硬过滤 + 向量语义 ----------
    @app.post("/api/recommend", response_model=RecommendResponse, tags=["推荐"])
    async def recommend(req: RecommendRequest) -> dict[str, Any]:
        """硬过滤（metadata）+ 向量语义检索（document）。"""
        try:
            return _get_recommender().recommend(
                query_text=req.query_text,
                filters=req.filters.model_dump(exclude_none=True),
                top_k=req.top_k,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"推荐失败: {exc}") from exc

    @app.post("/api/parse_intent", response_model=IntentResponse, tags=["意图解析"])
    async def parse_intent(req: ParseIntentRequest) -> dict[str, Any]:
        """LLM 解析用户输入，返回 filters + form 供前端回填。"""
        if _config is None:
            raise HTTPException(500, "应用未初始化")
        try:
            return parse_user_intent(_config, req.text)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"意图解析失败: {exc}") from exc

    @app.get("/api/random", response_model=RecipeItem, tags=["推荐"])
    async def random_recipe() -> dict[str, Any]:
        """从 SQLite 随机取一条（不走向量）。"""
        repo = _get_repo()
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
        if not row:
            raise HTTPException(404, "暂无菜谱数据")
        recipe = repo._row_to_dict(row)
        return {
            "id": recipe.get("id"),
            "title": recipe.get("title"),
            "decision_summary": recipe.get("decision_summary"),
            "cuisine_main": recipe.get("cuisine_main"),
            "greasiness": recipe.get("greasiness"),
            "spicy_level": recipe.get("spicy_level"),
            "ai_difficulty": recipe.get("ai_difficulty"),
            "estimated_time": recipe.get("estimated_time"),
            "allergens_str": recipe.get("allergens_str"),
            "diet_labels_str": recipe.get("diet_labels_str"),
            "ai_tags": recipe.get("ai_tags"),
            "image_url": recipe.get("image_url"),
            "source_url": recipe.get("source_url"),
            "ingredients": _ingredient_names(recipe.get("ingredients")),
        }

    @app.get(
        "/api/daily_recommendations",
        response_model=DailyResponse,
        tags=["推荐"],
    )
    async def daily_recommendations(
        limit: int = Query(5, ge=1, le=20),
    ) -> dict[str, Any]:
        """每日推荐：从 Chroma 取样并回 SQLite 补全。"""
        try:
            return _get_recommender().daily_recommendations(limit=limit)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"每日推荐失败: {exc}") from exc

    # ---------- 原有 SQLite 平铺列搜索 / 生成 / 对话 ----------
    @app.get(
        "/api/recipes/search",
        response_model=SearchRecipesResponse,
        tags=["菜谱"],
    )
    async def search_recipes(
        mood: str | None = None,
        taste: str | None = Query(None, description="逗号分隔口味，如 酸甜,蒜香"),
        health_goal: str | None = None,
        max_cook_minutes: int | None = Query(None, ge=1),
        spice_level: int | None = Query(None, ge=0, le=3),
        max_greasiness: int | None = Query(None, ge=1, le=5),
        ai_difficulty: str | None = Query(None, description="easy|medium|hard"),
        cuisine: str | None = None,
        exclude_allergens: str | None = Query(None, description="逗号分隔过敏原"),
        limit: int = Query(20, ge=1, le=100),
    ) -> dict[str, Any]:
        """基于 SQLite 平铺列筛选（不走向量）。"""
        taste_list = [t.strip() for t in (taste or "").split(",") if t.strip()] or None
        allergen_list = [
            a.strip() for a in (exclude_allergens or "").split(",") if a.strip()
        ] or None
        rows = _get_repo().filter_by_tags(
            mood=mood,
            taste=taste_list,
            health_goal=health_goal,
            max_cook_minutes=max_cook_minutes,
            spice_level=spice_level,
            max_greasiness=max_greasiness,
            ai_difficulty=ai_difficulty,
            cuisine=cuisine,
            exclude_allergens=allergen_list,
            limit=limit,
        )
        items = []
        for r in rows:
            items.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "cuisine": r.get("cuisine"),
                "cuisine_main": r.get("cuisine_main"),
                "greasiness": r.get("greasiness"),
                "spicy_level": r.get("spicy_level"),
                "ai_difficulty": r.get("ai_difficulty"),
                "estimated_time": r.get("estimated_time"),
                "cook_minutes": r.get("cook_minutes"),
                "decision_summary": r.get("decision_summary"),
                "diet_labels_str": r.get("diet_labels_str"),
                "allergens_str": r.get("allergens_str"),
                "image_url": r.get("image_url"),
                "source_url": r.get("source_url"),
            })
        return {"count": len(items), "items": items}

    @app.post("/api/recipes/generate", tags=["对话"])
    async def generate_recipe(req: GenerateRequest):
        return StreamingResponse(
            _get_generator().generate_stream(req),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/chat", tags=["对话"])
    async def chat(req: ChatRequest):
        return StreamingResponse(
            _get_generator().chat_stream(req),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/weather", response_model=WeatherResponse, tags=["辅助"])
    async def get_weather(city: str = Query(..., min_length=1)):
        if _weather is None:
            raise HTTPException(500, "天气服务未初始化")
        data = await _weather.get_weather(city)
        return WeatherResponse(**data)

    @app.get(
        "/api/sessions/{session_id}",
        response_model=SessionResponse,
        tags=["菜谱"],
    )
    async def get_session(session_id: str):
        session = _get_sessions().get(session_id)
        if not session:
            raise HTTPException(404, "会话不存在或已过期")
        return SessionResponse(
            session_id=session.session_id,
            form_context=session.form_context,
            messages=[SessionMessage(**m) for m in session.messages],
            last_recipe={"content": session.last_recipe} if session.last_recipe else None,
            sources=session.sources,
        )

    return app


app = create_app()
