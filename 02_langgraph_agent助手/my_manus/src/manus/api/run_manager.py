# -*- coding: utf-8 -*-
"""Run 持久化（SPEC §8.3）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from manus.pipeline.normalize import normalize_state_models
from manus.pipeline.state import PipelineState, create_initial_state


class RunManager:
    def __init__(self, runs_dir: Path | str):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, run_id: str) -> Path:
        d = self.runs_dir / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_state(self, state: PipelineState) -> None:
        state = normalize_state_models(state)
        path = self._run_dir(state.run_id) / "state.json"
        path.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_state(self, run_id: str) -> PipelineState:
        path = self.runs_dir / run_id / "state.json"
        if not path.is_file():
            raise FileNotFoundError(f"run 不存在: {run_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return normalize_state_models(PipelineState.model_validate(data))

    def append_log(self, run_id: str, message: str) -> None:
        log_path = self._run_dir(run_id) / "run.log"
        ts = datetime.now(timezone.utc).isoformat()
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")

    def create_run(self, run_date: str | None = None) -> PipelineState:
        state = create_initial_state(run_date=run_date)
        self.save_state(state)
        return state

    def list_runs(self, limit: int = 20, offset: int = 0) -> list[dict]:
        dirs = sorted(
            [p for p in self.runs_dir.iterdir() if p.is_dir()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        result: list[dict] = []
        for d in dirs[offset : offset + limit]:
            try:
                state = self.load_state(d.name)
                result.append(
                    {
                        "run_id": state.run_id,
                        "run_date": state.run_date,
                        "status": state.status,
                        "pending_approval_step": state.pending_approval_step,
                    }
                )
            except (FileNotFoundError, json.JSONDecodeError):
                continue
        return result
