# -*- coding: utf-8 -*-
"""用户账户相关 Pydantic 模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=72)


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenOnly(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPreferencesUpdate(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)


class UserPublic(BaseModel):
    id: int
    username: str
    email: str
    preferences: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class UserInDB(UserPublic):
    hashed_password: str
