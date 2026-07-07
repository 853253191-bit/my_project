# -*- coding: utf-8 -*-
"""Agent 执行过程进度上报（供 SSE / 页面展示）。"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

ProgressEmitter = Callable[..., None]

_ctx_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
_ctx_agent: ContextVar[int | None] = ContextVar("agent", default=None)
_ctx_emitter: ContextVar[ProgressEmitter | None] = ContextVar("emitter", default=None)


def bind_progress_context(
    run_id: str,
    agent: int,
    emitter: ProgressEmitter | None,
) -> tuple[Any, ...]:
    """绑定当前 Agent 的进度上下文，返回 token 元组用于 reset。"""
    return (
        _ctx_run_id.set(run_id),
        _ctx_agent.set(agent),
        _ctx_emitter.set(emitter),
    )


def reset_progress_context(tokens: tuple[Any, ...]) -> None:
    _ctx_run_id.reset(tokens[0])
    _ctx_agent.reset(tokens[1])
    _ctx_emitter.reset(tokens[2])


def emit_progress(message: str, *, kind: str = "progress") -> None:
    """上报 agent_progress / 思考片段。"""
    emitter = _ctx_emitter.get()
    if not emitter:
        return
    emitter(
        message=message,
        kind=kind,
        agent=_ctx_agent.get(),
        run_id=_ctx_run_id.get(),
    )


def has_progress_context() -> bool:
    return _ctx_emitter.get() is not None
