# -*- coding: utf-8 -*-
"""CLI 测试（SPEC §6.6）。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from manus.cli import cli


class TestCliRunCommands:
    def test_run_create(self, tmp_runs_dir, minimal_config_dict, monkeypatch):
        monkeypatch.setenv("MANUS_RUNS_DIR", str(tmp_runs_dir))
        runner = CliRunner()
        with patch("manus.cli.load_config", return_value=minimal_config_dict):
            result = runner.invoke(cli, ["run", "create", "--run-date", "2026-07-07"])
        assert result.exit_code == 0
        assert "run_id" in result.output.lower() or "run-" in result.output

    def test_run_list(self, tmp_runs_dir, minimal_config_dict, monkeypatch):
        monkeypatch.setenv("MANUS_RUNS_DIR", str(tmp_runs_dir))
        runner = CliRunner()
        with patch("manus.cli.load_config", return_value=minimal_config_dict):
            runner.invoke(cli, ["run", "create", "--run-date", "2026-07-07"])
            result = runner.invoke(cli, ["run", "list", "--limit", "5"])
        assert result.exit_code == 0

    def test_run_resolve_proceed(self, tmp_runs_dir, minimal_config_dict, monkeypatch):
        monkeypatch.setenv("MANUS_RUNS_DIR", str(tmp_runs_dir))
        runner = CliRunner()
        with patch("manus.cli.load_config", return_value=minimal_config_dict):
            create_out = runner.invoke(cli, ["run", "create", "--run-date", "2026-07-07"])
        # 从输出解析 run_id 由实现决定；此处 mock resolve
        with patch("manus.cli.PipelineRunner") as MockRunner:
            inst = MagicMock()
            inst.resolve_step = AsyncMock()
            MockRunner.return_value = inst
            with patch("manus.cli.load_config", return_value=minimal_config_dict):
                result = runner.invoke(
                    cli,
                    [
                        "run",
                        "resolve",
                        "--run-id",
                        "run-test",
                        "--step",
                        "0",
                        "--action",
                        "proceed",
                        "--news-id",
                        "news-1",
                    ],
                )
        assert result.exit_code == 0
