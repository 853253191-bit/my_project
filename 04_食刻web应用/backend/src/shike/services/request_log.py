# -*- coding: utf-8 -*-
"""统一请求日志字段，便于按 session_id / recipe_id / phase 排查。"""

from __future__ import annotations

import logging
from typing import Any, Sequence


def format_ids(ids: Sequence[Any] | None, *, limit: int = 8) -> str:
    """把菜谱 ID 列表收成日志友好字符串。"""
    if not ids:
        return "-"
    cleaned = [str(x).strip() for x in ids if x is not None and str(x).strip()]
    if not cleaned:
        return "-"
    head = cleaned[:limit]
    text = ",".join(head)
    if len(cleaned) > limit:
        text += f"...(+{len(cleaned) - limit})"
    return text


def log_api(
    logger: logging.Logger,
    phase: str,
    outcome: str,
    *,
    session_id: str | None = None,
    recipe_id: str | None = None,
    recipe_ids: Sequence[Any] | None = None,
    user_id: Any = None,
    extra: str = "",
    level: int = logging.INFO,
    exc_info: bool = False,
) -> None:
    """
    统一格式：
    phase=recommend ok | session_id=- | recipe_id=- | recipe_ids=a,b | user=3 | ...
    """
    rid = recipe_id if recipe_id else "-"
    if rid == "-" and recipe_ids:
        # 单条场景未传 recipe_id 时，用列表首个便于 grep
        first = next((str(x) for x in recipe_ids if x is not None and str(x).strip()), None)
        if first:
            rid = first

    msg = (
        f"phase={phase} {outcome} | "
        f"session_id={session_id or '-'} | "
        f"recipe_id={rid} | "
        f"recipe_ids={format_ids(recipe_ids)} | "
        f"user={user_id if user_id is not None else '-'}"
    )
    if extra:
        msg = f"{msg} | {extra}"
    logger.log(level, msg, exc_info=exc_info)
