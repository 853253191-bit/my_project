# -*- coding: utf-8 -*-
"""RunManager 持久化测试（SPEC §8.3）。"""

from __future__ import annotations

import json

import pytest

from manus.api.run_manager import RunManager
from manus.pipeline.state import create_initial_state


class TestRunManager:
    def test_create_and_load_state(self, tmp_runs_dir):
        mgr = RunManager(runs_dir=tmp_runs_dir)
        state = create_initial_state(run_id="run-persist-1", run_date="2026-07-07")
        mgr.save_state(state)
        loaded = mgr.load_state("run-persist-1")
        assert loaded.run_id == state.run_id
        assert loaded.run_date == state.run_date

    def test_state_json_on_disk(self, tmp_runs_dir):
        mgr = RunManager(runs_dir=tmp_runs_dir)
        state = create_initial_state(run_id="run-disk-1", run_date="2026-07-07")
        mgr.save_state(state)
        path = tmp_runs_dir / "run-disk-1" / "state.json"
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["run_id"] == "run-disk-1"

    def test_append_run_log(self, tmp_runs_dir):
        mgr = RunManager(runs_dir=tmp_runs_dir)
        mgr.append_log("run-log-1", "step0 completed")
        log_path = tmp_runs_dir / "run-log-1" / "run.log"
        assert log_path.is_file()
        assert "step0 completed" in log_path.read_text(encoding="utf-8")

    def test_list_runs(self, tmp_runs_dir):
        mgr = RunManager(runs_dir=tmp_runs_dir)
        for i in range(3):
            mgr.save_state(create_initial_state(run_id=f"run-{i}", run_date="2026-07-07"))
        runs = mgr.list_runs(limit=2)
        assert len(runs) == 2

    def test_load_missing_raises(self, tmp_runs_dir):
        mgr = RunManager(runs_dir=tmp_runs_dir)
        with pytest.raises(FileNotFoundError):
            mgr.load_state("nonexistent")
