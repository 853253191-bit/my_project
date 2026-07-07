# -*- coding: utf-8 -*-
"""Uvicorn 启动入口。"""

from __future__ import annotations

import os

import uvicorn

from manus.api.main import create_app
from manus.config import load_config


def main() -> None:
    cfg = load_config()
    runs_dir = os.getenv("MANUS_RUNS_DIR", "runs")
    app = create_app(runs_dir=runs_dir)
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port)


if __name__ == "__main__":
    main()
