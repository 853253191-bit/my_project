# -*- coding: utf-8 -*-
"""FastAPI 端点测试（SPEC §6.2 / §6.3，P2）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from manus.api.main import create_app


@pytest.fixture
def client(tmp_runs_dir, minimal_config_dict):
    app = create_app(config_dict=minimal_config_dict, runs_dir=tmp_runs_dir)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _mock_runner_step0(client):
    """避免测试环境真实调用 Agent1 / Tavily，并同步落盘 state。"""
    from manus.api import main as api_main
    from manus.pipeline.state import create_initial_state
    from manus.schemas.models import NewsItem

    done = create_initial_state(run_id="run-mock", run_date="2026-07-07")
    done.status = "awaiting_step_approval"
    done.pending_approval_step = 0
    done.news_items = [
        NewsItem(
            id="news-1",
            title="测试新闻",
            summary="摘要",
            source="test",
            url="https://example.com",
            published_at="2026-07-07T00:00:00Z",
            heat_score=0.8,
            relevance_tags=["AI"],
            hardware_focus=True,
            research_hint="hint",
        )
    ]
    done.step_output_summary = "采集硬件向新闻 1 条"

    rm = api_main._run_manager

    async def _fake_run_single_step(run_id: str, step: int):
        state = rm.load_state(run_id)
        state.status = done.status
        state.pending_approval_step = done.pending_approval_step
        state.news_items = done.news_items
        state.step_output_summary = done.step_output_summary
        rm.save_state(state)
        return state

    async def _fake_resolve(run_id: str, step: int, action: str, news_id: str | None = None):
        state = rm.load_state(run_id)
        if action == "proceed" and step == 0:
            state.status = "running"
            state.pending_approval_step = 0
            rm.save_state(state)
        state.status = "awaiting_step_approval"
        state.pending_approval_step = step if action == "rerun" else min(step + 1, 5)
        rm.save_state(state)
        return state

    with patch("manus.api.main.get_runner") as mock_get:
        mock_runner = MagicMock()
        mock_runner.run_single_step = AsyncMock(side_effect=_fake_run_single_step)
        mock_runner.resolve_step = AsyncMock(side_effect=_fake_resolve)
        mock_get.return_value = mock_runner
        yield mock_get


class TestHealthAndConfig:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_config_status(self, client: TestClient):
        resp = client.get("/config/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "workflow" in body or "step_approval_required" in str(body)


class TestRunsApi:
    def test_create_run(self, client: TestClient):
        resp = client.post("/runs", json={"run_date": "2026-07-07"})
        assert resp.status_code == 201
        body = resp.json()
        assert "run_id" in body
        assert body["status"] in ("pending", "awaiting_step_approval", "running")

    def test_get_run_not_found(self, client: TestClient):
        resp = client.get("/runs/missing-id")
        assert resp.status_code == 404

    def test_list_runs(self, client: TestClient):
        client.post("/runs", json={"run_date": "2026-07-07"})
        resp = client.get("/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestStepResolveApi:
    def test_resolve_endpoint_exists(self, client: TestClient):
        create = client.post("/runs", json={"run_date": "2026-07-07"})
        run_id = create.json()["run_id"]
        get_run = client.get(f"/runs/{run_id}")
        assert get_run.json()["status"] == "awaiting_step_approval"
        resp = client.post(
            f"/runs/{run_id}/steps/0/resolve",
            json={"action": "proceed", "news_id": "news-1"},
        )
        assert resp.status_code in (200, 202)
        assert resp.json().get("status") == "accepted"

    def test_step6_not_allowed(self, client: TestClient):
        create = client.post("/runs", json={"run_date": "2026-07-07"})
        run_id = create.json()["run_id"]
        resp = client.post(f"/runs/{run_id}/steps/6/resolve", json={"action": "proceed"})
        assert resp.status_code == 422


class TestStepApprovalView:
    def test_get_step_view(self, client: TestClient):
        create = client.post("/runs", json={"run_date": "2026-07-07"})
        run_id = create.json()["run_id"]
        resp = client.get(f"/runs/{run_id}/steps/0")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            body = resp.json()
            assert body["step"] == 0
            assert body["agent"] == 1


class TestLegacyCompat:
    def test_rerun_compat(self, client: TestClient):
        create = client.post("/runs", json={"run_date": "2026-07-07"})
        run_id = create.json()["run_id"]
        resp = client.post(f"/runs/{run_id}/rerun", params={"from": 2})
        assert resp.status_code in (200, 202, 404, 409)


class TestEventsApi:
    def test_events_history_after_create(self, client: TestClient):
        from manus.api import main as api_main

        create = client.post("/runs", json={"run_date": "2026-07-07"})
        run_id = create.json()["run_id"]
        hist = api_main._event_hub.history(run_id)
        assert any(h.get("event") == "run_start" for h in hist)

    def test_events_not_found(self, client: TestClient):
        resp = client.get("/runs/missing/events")
        assert resp.status_code == 404
