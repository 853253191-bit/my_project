# -*- coding: utf-8 -*-
"""FastAPI 入口（SPEC §6.2 / §6.3）。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from manus.api.events import RunEventHub
from manus.api.run_manager import RunManager
from manus.api.step_output import build_step_output
from manus.config import PROJECT_ROOT, AppConfig, config_to_dict, load_config
from manus.pipeline.constants import AGENT_NAMES, validate_step
from manus.pipeline.runner import PipelineRunner
from manus.schemas.models import ApprovalHints, StepApprovalView, StepResolveRequest

_app: FastAPI | None = None
_runner: PipelineRunner | None = None
_run_manager: RunManager | None = None
_event_hub: RunEventHub | None = None
_config: dict[str, Any] | AppConfig | None = None
_resolving_runs: set[str] = set()
APP_VERSION = "0.1.1"


class CreateRunRequest(BaseModel):
    run_date: str | None = None


def get_runner() -> PipelineRunner:
    if _runner is None:
        raise RuntimeError("应用未初始化")
    return _runner


def create_app(
    config_path: Path | str | None = None,
    config_dict: dict[str, Any] | None = None,
    runs_dir: Path | str | None = None,
) -> FastAPI:
    global _app, _runner, _run_manager, _event_hub, _config

    if config_dict is not None:
        _config = config_dict
    else:
        try:
            _config = load_config(config_path)
        except Exception:
            _config = {}

    runs_path = Path(runs_dir or os.getenv("MANUS_RUNS_DIR", PROJECT_ROOT / "runs"))
    _run_manager = RunManager(runs_path)
    _event_hub = RunEventHub()
    _runner = PipelineRunner(config=_config, run_manager=_run_manager, event_hub=_event_hub)

    app = FastAPI(title="Manus 产业链投研 Agent", version="0.1.0")

    async def _run_step_background(run_id: str, step: int) -> None:
        try:
            await get_runner().run_single_step(run_id, step)
        except Exception as exc:
            assert _run_manager is not None
            try:
                state = _run_manager.load_state(run_id)
                if state.status == "running":
                    state.status = "awaiting_step_approval"
                    state.pending_approval_step = step
                    state.errors.append(str(exc))
                    _run_manager.save_state(state)
            except FileNotFoundError:
                pass
            if _event_hub is not None:
                _event_hub.emit(run_id, "run_error", error=str(exc))

    async def _resolve_background(
        run_id: str,
        step: int,
        action: str,
        news_id: str | None,
    ) -> None:
        assert _run_manager is not None
        try:
            await get_runner().resolve_step(run_id, step, action, news_id=news_id)
        except Exception as exc:
            try:
                state = _run_manager.load_state(run_id)
                if state.status == "running":
                    state.status = "awaiting_step_approval"
                    state.pending_approval_step = step
                    state.errors.append(str(exc))
                    _run_manager.save_state(state)
            except FileNotFoundError:
                pass
            if _event_hub is not None:
                _event_hub.emit(run_id, "run_error", error=str(exc))
        finally:
            _resolving_runs.discard(run_id)

    static_dir = PROJECT_ROOT / "static"
    templates_dir = PROJECT_ROOT / "templates"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": APP_VERSION}

    @app.get("/config/status")
    def config_status():
        cfg = config_to_dict(_config) if _config else {}
        return {
            "workflow": cfg.get("workflow", {}),
            "step_approval_required": cfg.get("workflow", {}).get("step_approval_required", True),
            "llm_model": cfg.get("llm", {}).get("model", ""),
            "search_provider": cfg.get("search", {}).get("provider", ""),
        }

    @app.post("/runs", status_code=201)
    async def create_run(body: CreateRunRequest):
        """创建 run 并后台执行 Agent1（step0），前端通过 SSE 订阅进度。"""
        assert _run_manager is not None and _event_hub is not None
        state = _run_manager.create_run(run_date=body.run_date)
        state.status = "running"
        _run_manager.save_state(state)
        _event_hub.emit(
            state.run_id,
            "run_start",
            run_date=state.run_date,
            phase=state.phase,
        )
        asyncio.create_task(_run_step_background(state.run_id, 0))
        return state.model_dump(mode="json")

    @app.get("/runs/{run_id}/events")
    async def run_events(run_id: str):
        assert _run_manager is not None and _event_hub is not None
        try:
            _run_manager.load_state(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")
        return StreamingResponse(
            _event_hub.stream(run_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/runs")
    def list_runs(limit: int = 20, offset: int = 0):
        assert _run_manager is not None
        return _run_manager.list_runs(limit=limit, offset=offset)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        assert _run_manager is not None
        try:
            state = _run_manager.load_state(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")
        return state.model_dump(mode="json")

    @app.get("/runs/{run_id}/steps/{step}")
    def get_step_view(run_id: str, step: int):
        try:
            validate_step(step)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        assert _run_manager is not None
        try:
            state = _run_manager.load_state(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")
        if state.status != "awaiting_step_approval" or state.pending_approval_step != step:
            raise HTTPException(status_code=404, detail="当前步骤不可查看")
        output = build_step_output(state, step)
        view = StepApprovalView(
            run_id=run_id,
            step=step,
            agent=step + 1,
            agent_name=AGENT_NAMES[step],
            step_output_summary=state.step_output_summary or "",
            approval_hints=state.approval_hints or ApprovalHints(),
            output=output,
        )
        return view.model_dump(mode="json")

    @app.post("/runs/{run_id}/steps/{step}/resolve")
    async def resolve_step_endpoint(run_id: str, step: int, body: StepResolveRequest):
        try:
            validate_step(step)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        assert _run_manager is not None
        try:
            state = _run_manager.load_state(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")
        if state.status == "awaiting_step_approval":
            if state.pending_approval_step is not None and state.pending_approval_step != step:
                raise HTTPException(
                    status_code=409,
                    detail=f"待确认 step={state.pending_approval_step}，与请求不一致",
                )
            state.status = "running"
            _run_manager.save_state(state)
        elif state.status == "running":
            raise HTTPException(status_code=409, detail="run 正在执行中")
        else:
            raise HTTPException(status_code=409, detail=f"当前状态 {state.status} 不可 resolve")
        if run_id in _resolving_runs:
            raise HTTPException(status_code=409, detail="run 正在执行中")
        _resolving_runs.add(run_id)
        hints = state.approval_hints
        if body.action == "proceed" and hints is not None:
            block = hints.block_proceed if hasattr(hints, "block_proceed") else bool(hints.get("block_proceed"))
            if block:
                raise HTTPException(status_code=400, detail="block_proceed=true，禁止 proceed")
        if body.action == "proceed" and step == 0 and not body.news_id:
            raise HTTPException(status_code=400, detail="step0 proceed 必须提供 news_id")

        asyncio.create_task(
            _resolve_background(run_id, step, body.action, body.news_id)
        )
        return {"status": "accepted", "run_id": run_id, "step": step, "action": body.action}

    @app.post("/runs/{run_id}/rerun")
    async def rerun_compat(run_id: str, from_step: int = Query(..., alias="from")):
        try:
            validate_step(from_step)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        assert _run_manager is not None
        try:
            state = _run_manager.load_state(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")
        if state.status == "running":
            raise HTTPException(status_code=409, detail="run 正在执行中")
        state.status = "running"
        _run_manager.save_state(state)
        asyncio.create_task(_resolve_background(run_id, from_step, "rerun", None))
        return {"status": "accepted", "run_id": run_id, "step": from_step, "action": "rerun"}

    @app.get("/", response_class=HTMLResponse)
    def index():
        index_path = templates_dir / "index.html"
        if index_path.is_file():
            return index_path.read_text(encoding="utf-8")
        return "<html><body><h1>Manus Agent</h1><p>请配置 templates/index.html</p></body></html>"

    _app = app
    return app

