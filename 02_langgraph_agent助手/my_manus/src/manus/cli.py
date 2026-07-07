# -*- coding: utf-8 -*-
"""CLI 入口（SPEC §6.6）。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import click

from manus.api.run_manager import RunManager
from manus.config import PROJECT_ROOT, config_to_dict, load_config
from manus.pipeline.constants import AGENT_NAMES, step_to_agent
from manus.pipeline.runner import PipelineRunner


def _runs_dir() -> Path:
    return Path(os.getenv("MANUS_RUNS_DIR", PROJECT_ROOT / "runs"))


def _get_runner(cfg) -> PipelineRunner:
    mgr = RunManager(_runs_dir())
    return PipelineRunner(config=cfg, run_manager=mgr)


@click.group()
def cli():
    """Manus 产业链投研 Agent CLI。"""


@cli.group()
def run():
    """Run 管理命令。"""


@run.command("create")
@click.option("--run-date", default=None, help="运行日期 YYYY-MM-DD")
def run_create(run_date: str | None):
    cfg = load_config()
    if not isinstance(cfg, dict):
        cfg = config_to_dict(cfg)
    mgr = RunManager(_runs_dir())
    state = mgr.create_run(run_date=run_date)
    click.echo(f"run_id={state.run_id} status={state.status}")


@run.command("list")
@click.option("--limit", default=10, type=int)
def run_list(limit: int):
    mgr = RunManager(_runs_dir())
    for item in mgr.list_runs(limit=limit):
        click.echo(f"{item['run_id']}  {item['status']}  step={item.get('pending_approval_step')}")


@run.command("step-view")
@click.option("--run-id", required=True)
@click.option("--step", default=0, type=int)
def run_step_view(run_id: str, step: int):
    mgr = RunManager(_runs_dir())
    state = mgr.load_state(run_id)
    agent = step_to_agent(step)
    click.echo(f"run={run_id} step={step} agent={agent} name={AGENT_NAMES[step]}")
    click.echo(f"status={state.status} pending={state.pending_approval_step}")


@run.command("resolve")
@click.option("--run-id", required=True)
@click.option("--step", default=0, type=int)
@click.option("--action", type=click.Choice(["proceed", "rerun", "change_direction"]), required=True)
@click.option("--news-id", default=None)
def run_resolve(run_id: str, step: int, action: str, news_id: str | None):
    cfg = load_config()
    if not isinstance(cfg, dict):
        cfg = config_to_dict(cfg)
    runner = _get_runner(cfg)

    async def _go():
        return await runner.resolve_step(run_id, step, action, news_id=news_id)

    state = asyncio.run(_go())
    click.echo(f"resolved: status={state.status} pending={state.pending_approval_step}")


if __name__ == "__main__":
    cli()
