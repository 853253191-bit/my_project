# -*- coding: utf-8 -*-
"""单元/集成测试共享配置：把 backend/src 加入 sys.path。"""

from __future__ import annotations

import sys
from pathlib import Path

# 02_后端单元集成 → 04_mvp阶段测试 → test → 04_食刻web应用 → backend/src
ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent.parent
BACKEND_SRC = PROJECT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
