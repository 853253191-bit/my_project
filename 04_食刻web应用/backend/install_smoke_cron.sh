#!/usr/bin/env bash
# 薄包装：实际脚本已归档到 test/04_mvp阶段测试/01_后端API测试/
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ROOT}/test/04_mvp阶段测试/01_后端API测试/install_smoke_cron.sh"
exec bash "${TARGET}" "$@"
