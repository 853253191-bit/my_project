# -*- coding: utf-8 -*-
"""SSE 事件总线测试。"""

from __future__ import annotations

import asyncio

import pytest

from manus.api.events import RunEventHub


@pytest.mark.asyncio
async def test_emit_and_history():
    hub = RunEventHub()
    hub.emit("r1", "run_start", run_date="2026-07-07")
    hub.emit("r1", "agent_start", agent=1, agent_name="NewsCollector")
    hist = hub.history("r1")
    assert len(hist) == 2
    assert hist[0]["event"] == "run_start"
    assert hist[1]["agent"] == 1


@pytest.mark.asyncio
async def test_subscribe_replays_recent():
    hub = RunEventHub()
    hub.emit("r1", "run_start")
    q = await hub.subscribe("r1")
    item = await asyncio.wait_for(q.get(), timeout=1.0)
    assert item["event"] == "run_start"
    hub.unsubscribe("r1", q)


@pytest.mark.asyncio
async def test_stream_completes_on_run_complete():
    hub = RunEventHub()

    async def _consume():
        lines: list[str] = []
        async for line in hub.stream("r1"):
            lines.append(line)
            if "run_complete" in line:
                break
        return lines

    hub.emit("r1", "run_start")
    consumer = asyncio.create_task(_consume())
    await asyncio.sleep(0.02)
    hub.emit("r1", "run_complete")
    lines = await asyncio.wait_for(consumer, timeout=2.0)
    assert any("run_complete" in ln for ln in lines)
