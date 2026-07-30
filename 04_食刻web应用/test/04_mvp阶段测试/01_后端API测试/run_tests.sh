#!/usr/bin/env bash
# =============================================================================
# 食刻 · 后端 API 黑盒测试运行脚本
# 位置：test/04_mvp阶段测试/01_后端API测试/
# 用法：
#   ./run_tests.sh              # 默认：冒烟 + 过滤 + 扩召回（不含慢语义）
#   ./run_tests.sh --smoke      # 仅冒烟
#   ./run_tests.sh --full       # 完整测试集
#   ./run_tests.sh --report     # 生成 HTML + JUnit 报告
#   ./run_tests.sh --failfast   # 首个失败即停
# 环境变量：
#   TEST_ENV=production         # 测公网
#   TEST_BASE_URL=http://...    # 自定义 API
#   ALERT_ON_FAIL=1             # 失败时调用 alert.sh
# =============================================================================

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[FAIL]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# 01_后端API测试 → 04_mvp阶段测试 → test → 项目根
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
REPORTS_DIR="${SCRIPT_DIR}/e2e_api/reports"
mkdir -p "${REPORTS_DIR}"

MODE="default"
WANT_REPORT=0
FAILFAST=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke) MODE="smoke"; shift ;;
    --full) MODE="full"; shift ;;
    --report) WANT_REPORT=1; shift ;;
    --failfast) FAILFAST=1; shift ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# //;s/^#//'
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# 优先使用 backend 虚拟环境
PYTHON="python3"
if [[ -x "${BACKEND_DIR}/venv/bin/python" ]]; then
  PYTHON="${BACKEND_DIR}/venv/bin/python"
elif [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  PYTHON="${BACKEND_DIR}/.venv/bin/python"
elif [[ -x "${SCRIPT_DIR}/venv/bin/python" ]]; then
  PYTHON="${SCRIPT_DIR}/venv/bin/python"
fi

info "Python: ${PYTHON}"
info "MODE=${MODE} TEST_ENV=${TEST_ENV:-local} BASE=${TEST_BASE_URL:-auto}"
info "用例目录: ${SCRIPT_DIR}/e2e_api"

# 安装测试依赖（缺失时）
REQ_FILE="${SCRIPT_DIR}/requirements-test.txt"
if ! "${PYTHON}" -c "import pytest, requests" 2>/dev/null; then
  info "安装测试依赖 requirements-test.txt ..."
  "${PYTHON}" -m pip install -q -r "${REQ_FILE}"
fi
if [[ "${WANT_REPORT}" -eq 1 ]]; then
  if ! "${PYTHON}" -c "import pytest_html" 2>/dev/null; then
    "${PYTHON}" -m pip install -q pytest-html
  fi
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
JUNIT_XML="${REPORTS_DIR}/junit_${STAMP}.xml"
HTML_REPORT="${REPORTS_DIR}/report_${STAMP}.html"

PYTEST_ARGS=(-v --tb=short "--junitxml=${JUNIT_XML}")

case "${MODE}" in
  smoke|default)
    # 冒烟：健康 + 过滤 + 扩召回（不含慢语义）
    PYTEST_ARGS+=(-m "smoke")
    ;;
  full)
    # 完整：跑 e2e_api 下全部 API 用例（含 semantic）
    PYTEST_ARGS+=("e2e_api/test_health.py" "e2e_api/test_filters.py" "e2e_api/test_semantic.py" "e2e_api/test_expand.py")
    ;;
esac

if [[ "${FAILFAST}" -eq 1 ]]; then
  PYTEST_ARGS+=(--maxfail=1)
fi

if [[ "${WANT_REPORT}" -eq 1 ]]; then
  PYTEST_ARGS+=(--html="${HTML_REPORT}" --self-contained-html)
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  PYTEST_ARGS+=("${EXTRA_ARGS[@]}")
fi

info "执行: ${PYTHON} -m pytest ${PYTEST_ARGS[*]}"
set +e
"${PYTHON}" -m pytest "${PYTEST_ARGS[@]}"
CODE=$?
set -e

PASSED=0
FAILED=0
SKIPPED=0
if [[ -f "${JUNIT_XML}" ]]; then
  SUMMARY_LINE="$(grep -oE 'tests="[0-9]+"|failures="[0-9]+"|errors="[0-9]+"|skipped="[0-9]+"' "${JUNIT_XML}" | tr '\n' ' ')"
  TESTS_N="$(echo "${SUMMARY_LINE}" | grep -oE 'tests="[0-9]+"' | head -1 | grep -oE '[0-9]+' || echo 0)"
  FAIL_N="$(echo "${SUMMARY_LINE}" | grep -oE 'failures="[0-9]+"' | head -1 | grep -oE '[0-9]+' || echo 0)"
  ERR_N="$(echo "${SUMMARY_LINE}" | grep -oE 'errors="[0-9]+"' | head -1 | grep -oE '[0-9]+' || echo 0)"
  SKIP_N="$(echo "${SUMMARY_LINE}" | grep -oE 'skipped="[0-9]+"' | head -1 | grep -oE '[0-9]+' || echo 0)"
  FAILED=$((FAIL_N + ERR_N))
  SKIPPED=${SKIP_N}
  PASSED=$((TESTS_N - FAILED - SKIPPED))
  if [[ "${PASSED}" -lt 0 ]]; then PASSED=0; fi
fi

echo ""
echo "=============================================="
if [[ "${CODE}" -eq 0 ]]; then
  ok "通过 ${PASSED} 个，失败 ${FAILED} 个，跳过 ${SKIPPED} 个"
else
  err "通过 ${PASSED} 个，失败 ${FAILED} 个，跳过 ${SKIPPED} 个"
fi
info "JUnit: ${JUNIT_XML}"
if [[ "${WANT_REPORT}" -eq 1 && -f "${HTML_REPORT}" ]]; then
  info "HTML:  ${HTML_REPORT}"
fi
info "失败详情目录: ${REPORTS_DIR}/fail_*.json"
echo "=============================================="

# 失败告警：优先本目录，其次 backend/alert.sh
ALERT_SCRIPT="${SCRIPT_DIR}/alert.sh"
if [[ ! -f "${ALERT_SCRIPT}" ]]; then
  ALERT_SCRIPT="${BACKEND_DIR}/alert.sh"
fi
if [[ ! -x "${ALERT_SCRIPT}" && -f "${ALERT_SCRIPT}" ]]; then
  chmod +x "${ALERT_SCRIPT}" || true
fi
if [[ "${CODE}" -ne 0 && "${ALERT_ON_FAIL:-0}" == "1" && -f "${ALERT_SCRIPT}" ]]; then
  warn "测试失败，触发告警 ..."
  bash "${ALERT_SCRIPT}" --smoke-failed --message "食刻测试失败 MODE=${MODE} passed=${PASSED} failed=${FAILED} skipped=${SKIPPED}"
fi

exit "${CODE}"
