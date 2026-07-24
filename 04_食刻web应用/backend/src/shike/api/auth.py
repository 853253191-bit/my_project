# -*- coding: utf-8 -*-
"""认证 API：注册 / 登录 / 刷新 / 当前用户。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shike.api.dependencies import get_current_user, get_user_store
from shike.models.user import (
    AccessTokenOnly,
    TokenPair,
    TokenRefresh,
    UserLogin,
    UserPreferencesUpdate,
    UserPublic,
    UserRegister,
)
from shike.services.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    safe_decode,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "preferences": user.get("preferences") or {},
        "is_active": bool(user.get("is_active", True)),
    }


@router.post("/register")
async def register(body: UserRegister) -> dict[str, Any]:
    """注册新用户。"""
    store = get_user_store()
    if store.get_by_username(body.username):
        raise HTTPException(400, "用户名已存在")
    if store.get_by_email(str(body.email)):
        raise HTTPException(400, "邮箱已注册")
    user = store.create_user(
        username=body.username.strip(),
        email=str(body.email).strip().lower(),
        hashed_password=hash_password(body.password),
    )
    logger.info("auth register | user_id=%s username=%s", user["id"], user["username"])
    return {"user_id": user["id"], "username": user["username"]}


@router.post("/login", response_model=TokenPair)
async def login(body: UserLogin) -> dict[str, Any]:
    """用户名密码登录，返回 Access + Refresh Token。"""
    store = get_user_store()
    user = store.get_by_username(body.username.strip())
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(401, "用户名或密码错误")
    if not user.get("is_active"):
        raise HTTPException(403, "账号已禁用")
    access = create_access_token(user["id"], user["username"])
    refresh = create_refresh_token(user["id"], user["username"])
    logger.info("auth login | user_id=%s", user["id"])
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=AccessTokenOnly)
async def refresh_token(body: TokenRefresh) -> dict[str, Any]:
    """用 Refresh Token 换取新的 Access Token。"""
    payload = safe_decode(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "无效的刷新令牌")
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, "无效的刷新令牌") from exc
    user = get_user_store().get_by_id(user_id)
    if not user or not user.get("is_active"):
        raise HTTPException(401, "用户不存在或已禁用")
    access = create_access_token(user["id"], user["username"])
    return {"access_token": access, "token_type": "bearer"}


@router.get("/me", response_model=UserPublic)
async def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """获取当前登录用户信息。"""
    return _public_user(user)


@router.put("/me")
async def update_me(
    body: UserPreferencesUpdate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """更新当前用户偏好。"""
    updated = get_user_store().update_preferences(user["id"], body.preferences or {})
    if not updated:
        raise HTTPException(404, "用户不存在")
    logger.info("auth update preferences | user_id=%s", user["id"])
    return {
        "id": updated["id"],
        "preferences": updated.get("preferences") or {},
    }
