# -*- coding: utf-8 -*-
"""API 响应模型（供 Swagger / OpenAPI 展示与前端类型生成）。

字段与现有接口实际返回保持一致，避免 response_model 裁剪业务字段。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RecipeItem(BaseModel):
    """推荐 / 随机菜品条目。"""

    id: str
    title: str = ""
    decision_summary: str | None = None
    reason: str | None = None
    greasiness: int | None = None
    spicy_level: int | None = None
    ai_difficulty: str | None = None
    estimated_time: int | None = None
    cuisine_main: str | None = None
    allergens_str: str | None = None
    diet_labels_str: str | None = None
    ai_tags: dict[str, Any] | None = None
    image_url: str | None = None
    source_url: str | None = None
    distance: float | None = None
    preference_score: float | None = None
    final_score: float | None = None
    ingredients: list[str] = Field(default_factory=list)
    is_favorited: bool | None = None


class RecommendResponse(BaseModel):
    """POST /api/recommend 响应。"""

    items: list[RecipeItem] = Field(default_factory=list)
    count: int = 0
    message: str = ""
    recall_level: int | None = None


class FeedbackResponse(BaseModel):
    """POST /api/feedback 响应。"""

    ok: bool = True
    id: int = 0
    message: str = "反馈已记录"


class DailyItem(BaseModel):
    """GET /api/daily_recommendations 单条。"""

    id: str
    title: str = ""
    decision_summary: str | None = None
    cuisine_main: str | None = None
    estimated_time: int | None = None
    ai_difficulty: str | None = None
    image_url: str | None = None
    ingredients: list[str] = Field(default_factory=list)


class DailyResponse(BaseModel):
    """GET /api/daily_recommendations 响应。"""

    items: list[DailyItem] = Field(default_factory=list)
    count: int = 0


class IntentForm(BaseModel):
    """意图解析回填表单。"""

    mood: str | None = None
    taste: list[str] = Field(default_factory=list)
    spice_level: int | None = None
    servings: int | None = None
    cook_time: str | None = None
    health_goal: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    free_text: str | None = None


class IntentResponse(BaseModel):
    """POST /api/parse_intent 响应。"""

    query_text: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)
    form: IntentForm = Field(default_factory=IntentForm)


class HealthResponse(BaseModel):
    """GET /api/health 响应。"""

    status: str
    version: str
    recipe_count: int = 0
    chroma_count: int = 0


class SearchRecipeItem(BaseModel):
    """GET /api/recipes/search 单条。"""

    id: str
    title: str = ""
    cuisine: str | None = None
    cuisine_main: str | None = None
    greasiness: int | None = None
    spicy_level: int | None = None
    ai_difficulty: str | None = None
    estimated_time: int | None = None
    cook_minutes: int | None = None
    decision_summary: str | None = None
    diet_labels_str: str | None = None
    allergens_str: str | None = None
    image_url: str | None = None
    source_url: str | None = None


class SearchRecipesResponse(BaseModel):
    """GET /api/recipes/search 响应。"""

    count: int = 0
    items: list[SearchRecipeItem] = Field(default_factory=list)


class RecipeDetailResponse(BaseModel):
    """GET /api/recipes/{id} 详情（库内直出，不调 LLM）。"""

    id: str
    title: str = ""
    content: str = ""
    session_id: str = ""
    decision_summary: str | None = None
    cuisine_main: str | None = None
    estimated_time: int | None = None
    ai_difficulty: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    steps: list[Any] = Field(default_factory=list)


class SiteFeedbackCreate(BaseModel):
    """POST /api/site-feedback 提交站点意见。"""

    content: str = Field(..., min_length=5, max_length=2000, description="意见正文")
    contact: str | None = Field(None, max_length=120, description="可选联系方式")
    category: str = Field("建议", max_length=20, description="建议|问题|表扬|其他")


class SiteFeedbackItem(BaseModel):
    """站点反馈单条。"""

    id: int
    content: str
    contact: str | None = None
    category: str = "建议"
    user_id: str | None = None
    username: str | None = None
    status: str = "pending"
    created_at: str | None = None


class SiteFeedbackListResponse(BaseModel):
    """GET /api/site-feedback 列表。"""

    items: list[SiteFeedbackItem] = Field(default_factory=list)
    total: int = 0


class SiteFeedbackSubmitResponse(BaseModel):
    """POST /api/site-feedback 响应。"""

    ok: bool = True
    id: int = 0
    message: str = "感谢反馈，我们会认真阅读"
