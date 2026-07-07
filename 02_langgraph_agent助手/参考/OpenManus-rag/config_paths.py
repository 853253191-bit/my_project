# -*- coding: utf-8 -*-
"""案例目录路径配置，供 scripts/ 下各脚本统一引用。"""

from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parent
KNOWLEDGE_DIR = CASE_ROOT / "knowledge"
STATIC_DIR = CASE_ROOT / "static"
