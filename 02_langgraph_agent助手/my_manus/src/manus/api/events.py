# -*- coding: utf-8 -*-
"""Run 级 SSE 事件总线（SPEC §6.3）。"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, AsyncIterator


class RunEventHub:
    """按 run_id 分发事件，支持多订阅者与历史回放。"""

    def __init__(self, history_limit: int = 200) -> None:
        self._history_limit = history_limit
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    @staticmethod
    def _ts() -> str:
        return datetime.now(timezone.utc).isoformat()

    def emit(self, run_id: str, event: str, **payload: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "event": event,
            "run_id": run_id,
            "timestamp": self._ts(),
            **payload,
        }
        hist = self._history[run_id]
        hist.append(data)
        if len(hist) > self._history_limit:
            self._history[run_id] = hist[-self._history_limit :]
        for q in self._queues.get(run_id, []):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass
        return data

    def history(self, run_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(run_id, []))

    async def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        self._queues[run_id].append(q)
        for item in self._history.get(run_id, [])[-50:]:
            await q.put(item)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._queues.get(run_id, [])
        if q in subs:
            subs.remove(q)

    async def stream(self, run_id: str) -> AsyncIterator[str]:
        q = await self.subscribe(run_id)
        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    hb = {"event": "heartbeat", "run_id": run_id, "timestamp": self._ts()}
                    yield f"data: {json.dumps(hb, ensure_ascii=False)}\n\n"
                    continue
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                if data.get("event") == "run_complete":
                    break
        finally:
            self.unsubscribe(run_id, q)
