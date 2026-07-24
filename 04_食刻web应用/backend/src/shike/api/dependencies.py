# -*- coding: utf-8 -*-
"""FastAPI 依赖：当前用户 / 可选用户。"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shike.services.security import safe_decode

_bearer = HTTPBearer(auto_error=False)
_user_store_getter: Callable[[], Any] | None = None


def set_user_store_getter(getter: Callable[[], Any]) -> None:
    global _user_store_getter
    _user_store_getter = getter


def get_user_store():
    if _user_store_getter is None:
        raise HTTPException(500, "用户存储未初始化")
    return _user_store_getter()


def _user_from_token(token: str) -> dict[str, Any]:
    payload = safe_decode(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的访问令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, "无效的令牌主体") from exc
    user = get_user_store().get_by_id(user_id)
    if not user or not user.get("is_active"):
        raise HTTPException(401, "用户不存在或已禁用")
    return user


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """受保护路由：必须携带有效 Access Token。"""
    if cred is None or not cred.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_token(cred.credentials)


async def get_optional_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """可选登录：无 Token 时返回 None，不抛错。"""
    if cred is None or not cred.credentials:
        return None
    payload = safe_decode(cred.credentials)
    if not payload or payload.get("type") != "access":
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = get_user_store().get_by_id(user_id)
    if not user or not user.get("is_active"):
        return None
    return user
