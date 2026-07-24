# -*- coding: utf-8 -*-
"""密码哈希与 JWT 签发/校验。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))


def get_jwt_secret() -> str:
    """JWT 密钥，生产环境务必设置 JWT_SECRET。"""
    return (
        os.getenv("JWT_SECRET", "").strip()
        or "shike-dev-jwt-secret-change-me-in-production"
    )


def hash_password(password: str) -> str:
    # bcrypt 最长 72 字节
    raw = (password or "")[:72]
    return pwd_context.hash(raw)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify((plain or "")[:72], hashed)


def create_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def create_access_token(user_id: int, username: str) -> str:
    return create_token(
        subject=str(user_id),
        token_type="access",
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        extra={"username": username},
    )


def create_refresh_token(user_id: int, username: str) -> str:
    return create_token(
        subject=str(user_id),
        token_type="refresh",
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        extra={"username": username},
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])


def safe_decode(token: str) -> dict[str, Any] | None:
    try:
        return decode_token(token)
    except JWTError:
        return None
