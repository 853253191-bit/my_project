# -*- coding: utf-8 -*-
"""应用启动入口。

可直接运行本文件，也可：
  cd backend
  set PYTHONPATH=src
  python -m shike.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# 直接运行 main.py 时，把 src 加入模块搜索路径
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from dotenv import load_dotenv
import uvicorn

from shike.config import load_config, PROJECT_ROOT

# 加载项目根目录与 backend 下的 .env
load_dotenv(PROJECT_ROOT.parent / ".env")
load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    cfg = load_config()
    uvicorn.run(
        "shike.api.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
