# -*- coding: utf-8 -*-
"""收藏夹请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FavoriteCreate(BaseModel):
    recipe_id: str = Field(..., min_length=1)


class FavoriteItem(BaseModel):
    favorite_id: int
    recipe_id: str
    created_at: str | None = None
    title: str | None = None
    decision_summary: str | None = None
    cuisine_main: str | None = None
    estimated_time: int | None = None
    image_url: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    recipe: dict[str, Any] | None = None


class FavoriteListResponse(BaseModel):
    items: list[FavoriteItem] = Field(default_factory=list)
    total: int = 0


class FavoriteCheckResponse(BaseModel):
    is_favorited: bool
