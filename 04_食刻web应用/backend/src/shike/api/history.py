# -*- coding: utf-8 -*-
"""浏览历史 API。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from shike.api.dependencies import get_current_user, get_user_store
from shike.models.history import HistoryCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["历史"])


@router.post("")
async def add_history(
    body: HistoryCreate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """添加浏览记录。"""
    hid = get_user_store().add_history(
        user["id"], body.recipe_id, body.query_text
    )
    logger.info(
        "history add | phase=history session_id=- recipe_id=%s user=%s history_id=%s",
        body.recipe_id,
        user["id"],
        hid,
    )
    return {"history_id": hid}


@router.get("")
async def list_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """分页获取历史记录。"""
    items, total = get_user_store().list_history(
        user["id"], page=page, limit=limit
    )
    return {"items": items, "total": total}


@router.delete("")
async def clear_history(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """清空当前用户历史记录。"""
    n = get_user_store().clear_history(user["id"])
    logger.info("history clear | user_id=%s deleted=%s", user["id"], n)
    return {"message": "历史记录已清空"}
