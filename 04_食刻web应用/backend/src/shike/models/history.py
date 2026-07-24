# -*- coding: utf-8 -*-
"""浏览历史请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HistoryCreate(BaseModel):
    recipe_id: str = Field(..., min_length=1)
    query_text: str | None = None


class HistoryItem(BaseModel):
    history_id: int
    recipe_id: str
    query_text: str | None = None
    created_at: str | None = None
    title: str | None = None
    decision_summary: str | None = None
    cuisine_main: str | None = None
    estimated_time: int | None = None
    image_url: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    recipe: dict[str, Any] | None = None


class HistoryListResponse(BaseModel):
    items: list[HistoryItem] = Field(default_factory=list)
    total: int = 0
