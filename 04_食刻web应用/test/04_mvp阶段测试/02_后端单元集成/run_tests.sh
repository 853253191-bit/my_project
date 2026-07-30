#!/usr/bin/env bash
# 运行后端离线单元/集成测试
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

PYTHON="python3"
if [[ -x "${BACKEND_DIR}/venv/bin/python" ]]; then
  PYTHON="${BACKEND_DIR}/venv/bin/python"
elif [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  PYTHON="${BACKEND_DIR}/.venv/bin/python"
fi

cd "${SCRIPT_DIR}"
if ! "${PYTHON}" -c "import pytest" 2>/dev/null; then
  "${PYTHON}" -m pip install -q -r "${SCRIPT_DIR}/requirements-test.txt"
fi
# 业务依赖（security / repository）来自 backend 环境
export PYTHONPATH="${BACKEND_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
exec "${PYTHON}" -m pytest "$@"
