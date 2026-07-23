# -*- coding: utf-8 -*-
"""会话管理（内存存储）。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from shike.config import AppConfig


@dataclass
class Session:
    session_id: str
    form_context: dict[str, Any] | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    last_recipe: str = ""
    sources: list[dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class SessionManager:
    def __init__(self, config: AppConfig):
        self._sessions: dict[str, Session] = {}
        self._max_history = config.session.max_history
        self._ttl = config.session.ttl_hours * 3600

    def create(self, form_context: dict[str, Any] | None = None) -> Session:
        sid = f"sess_{uuid4().hex[:12]}"
        session = Session(session_id=sid, form_context=form_context)
        self._sessions[sid] = session
        self._cleanup()
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session and time.time() - session.created_at > self._ttl:
            del self._sessions[session_id]
            return None
        return session

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get(session_id)
        if not session:
            return
        session.messages.append({"role": role, "content": content})
        if len(session.messages) > self._max_history * 2:
            session.messages = session.messages[-self._max_history * 2 :]

    def update_recipe(self, session_id: str, recipe: str, sources: list[dict[str, str]]) -> None:
        session = self.get(session_id)
        if session:
            session.last_recipe = recipe
            session.sources = sources

    def _cleanup(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.created_at > self._ttl]
        for sid in expired:
            del self._sessions[sid]
