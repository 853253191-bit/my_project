# -*- coding: utf-8 -*-
"""API 请求/响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GenerateRequest(BaseModel):
    mood: str
    taste: list[str] = Field(default_factory=list)
    spice_level: int = Field(default=0, ge=0, le=3)
    servings: int = Field(default=2, ge=1, le=8)
    cook_time: str = "30分钟内"
    health_goal: str = "无"
    ingredients: list[str] = Field(default_factory=list)
    city: str = ""
    free_text: str = ""


class ChatRequest(BaseModel):
    session_id: str
    message: str


class RecipeSource(BaseModel):
    id: str
    title: str
    source_url: str = ""


class SessionMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SessionResponse(BaseModel):
    session_id: str
    form_context: dict[str, Any] | None = None
    messages: list[SessionMessage] = Field(default_factory=list)
    last_recipe: dict[str, Any] | None = None
    sources: list[RecipeSource] = Field(default_factory=list)


class WeatherResponse(BaseModel):
    city: str
    weather: str
    temperature: str
    report_time: str = ""


class RecommendFilters(BaseModel):
    """硬过滤条件（对应 Chroma metadata / SQLite 平铺列）。"""

    greasiness_max: int | None = Field(default=None, ge=1, le=5)
    spicy_level_max: int | None = Field(default=None, ge=0, le=5)
    cuisine_main: str | None = Field(default=None, description="菜系，如川菜；未使用请填 null，勿留 string")
    ai_difficulty: str | None = Field(
        default=None, description="easy|medium|hard；未使用请填 null，勿留 string"
    )
    estimated_time_max: int | None = Field(default=None, ge=1)
    exclude_allergens: list[str] = Field(default_factory=list)
    include_diet_labels: list[str] = Field(default_factory=list)

    @field_validator("cuisine_main", "ai_difficulty", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: Any) -> Any:
        """Swagger 占位 'string' / 空串视为未设置，避免硬过滤匹配不到任何菜。"""
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s or s.lower() in {"string", "null", "none"}:
                return None
            return s
        return v

    @field_validator("exclude_allergens", "include_diet_labels", mode="before")
    @classmethod
    def _clean_str_list(cls, v: Any) -> Any:
        if not v:
            return []
        if not isinstance(v, list):
            return v
        out: list[str] = []
        for item in v:
            s = str(item).strip()
            if not s or s.lower() in {"string", "null", "none"}:
                continue
            out.append(s)
        return out


class RecommendRequest(BaseModel):
    """混合检索请求：query_text 走向量，filters 走硬过滤。"""

    query_text: str = Field(..., min_length=1, examples=["清淡家常菜"])
    filters: RecommendFilters = Field(default_factory=RecommendFilters)
    top_k: int = Field(default=3, ge=1, le=20)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query_text": "随便吃点",
                    "filters": {
                        "spicy_level_max": 0,
                        "exclude_allergens": ["鸡蛋"],
                    },
                    "top_k": 3,
                }
            ]
        }
    }


class ParseIntentRequest(BaseModel):
    text: str = Field(..., min_length=1)
