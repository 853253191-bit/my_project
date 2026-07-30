# -*- coding: utf-8 -*-
"""密码哈希与 JWT 单元测试。"""

from __future__ import annotations

from shike.services.security import (
    create_access_token,
    hash_password,
    safe_decode,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token(42, "leo")
    payload = safe_decode(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["username"] == "leo"
    assert payload["type"] == "access"


def test_safe_decode_invalid_token():
    assert safe_decode("not.a.jwt") is None
