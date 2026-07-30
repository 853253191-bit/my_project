#!/usr/bin/env bash
# 薄包装：实际用例已归档到 test/04_mvp阶段测试/01_后端API测试/
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ROOT}/test/04_mvp阶段测试/01_后端API测试/run_tests.sh"
exec bash "${TARGET}" "$@"
