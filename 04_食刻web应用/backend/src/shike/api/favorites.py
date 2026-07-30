# -*- coding: utf-8 -*-
"""收藏夹 API。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from shike.api.dependencies import get_current_user, get_user_store
from shike.models.favorite import FavoriteCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/favorites", tags=["收藏"])


@router.post("")
async def add_favorite(
    body: FavoriteCreate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """添加收藏。"""
    store = get_user_store()
    fid = store.add_favorite(user["id"], body.recipe_id)
    logger.info(
        "favorite add | phase=favorite session_id=- recipe_id=%s user=%s favorite_id=%s",
        body.recipe_id,
        user["id"],
        fid,
    )
    return {"favorite_id": fid, "recipe_id": body.recipe_id}


@router.delete("/{recipe_id}")
async def remove_favorite(
    recipe_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """取消收藏。"""
    ok = get_user_store().remove_favorite(user["id"], recipe_id)
    if not ok:
        raise HTTPException(404, "未找到收藏记录")
    logger.info(
        "favorite remove | phase=favorite session_id=- recipe_id=%s user=%s",
        recipe_id,
        user["id"],
    )
    return {"message": "已取消收藏"}


@router.get("")
async def list_favorites(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """分页获取收藏列表。"""
    items, total = get_user_store().list_favorites(
        user["id"], page=page, limit=limit
    )
    return {"items": items, "total": total}


@router.get("/check/{recipe_id}")
async def check_favorite(
    recipe_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """检查是否已收藏。"""
    return {
        "is_favorited": get_user_store().is_favorited(user["id"], recipe_id),
    }
