#!/usr/bin/env bash
# =============================================================================
# 食刻 · 服务状态检查（稳住底盘）
# 安装位置建议：/opt/shike/status.sh
# 用法：./status.sh
# =============================================================================

set -uo pipefail
# 不用 set -e：单项失败继续检查并汇总

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ️  $*${NC}"; }
ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
bad()  { echo -e "${RED}❌ $*${NC}"; }

SERVICE_NAME="${SERVICE_NAME:-shike-backend}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/health}"
PASS=0
FAIL=0

check_pass() { PASS=$((PASS + 1)); ok "$1"; }
check_fail() { FAIL=$((FAIL + 1)); bad "$1"; }

echo "=============================================="
echo " 食刻 · 服务状态检查"
echo "=============================================="
echo ""

# --- Nginx ---
nginx_state="$(systemctl is-active nginx 2>/dev/null || echo inactive)"
if [[ "${nginx_state}" == "active" ]]; then
  check_pass "Nginx：active (running)"
else
  check_fail "Nginx：${nginx_state}（查看: sudo systemctl status nginx）"
fi

# --- 后端 ---
backend_state="$(systemctl is-active "${SERVICE_NAME}" 2>/dev/null || echo inactive)"
if [[ "${backend_state}" == "active" ]]; then
  check_pass "后端 ${SERVICE_NAME}：active (running)"
else
  check_fail "后端 ${SERVICE_NAME}：${backend_state}（查看: ./logs.sh backend 50）"
fi

# --- 端口 ---
ss_out="$(ss -tlnp 2>/dev/null || true)"
if echo "${ss_out}" | grep -qE ':80\s'; then
  check_pass "80 端口：已监听"
else
  check_fail "80 端口：未监听（检查 Nginx / 安全组）"
fi

if echo "${ss_out}" | grep -qE ':8000\s'; then
  check_pass "8000 端口：已监听"
else
  check_fail "8000 端口：未监听（检查 shike-backend）"
fi

# --- 健康检查 ---
http_code="$(curl -sS -o /tmp/shike_health_body.txt -w "%{http_code}" --max-time 8 "${HEALTH_URL}" 2>/dev/null || echo "000")"
if [[ "${http_code}" == "200" ]]; then
  check_pass "本地 API 健康检查：HTTP ${http_code}"
  body="$(cat /tmp/shike_health_body.txt 2>/dev/null || true)"
  echo "     响应: ${body}"
else
  check_fail "本地 API 健康检查：HTTP ${http_code}（检查 Nginx 反代与后端）"
  echo "     提示: curl -s ${HEALTH_URL}"
fi

# --- 最近错误 ---
echo ""
info "后端最近错误相关日志（最多 10 条匹配）："
err_lines="$(sudo journalctl -u "${SERVICE_NAME}" -n 80 --no-pager 2>/dev/null | grep -iE 'error|traceback|exception|fail' | tail -n 10 || true)"
if [[ -n "${err_lines}" ]]; then
  warn "发现可能异常："
  echo "${err_lines}"
  echo "     完整日志: ./logs.sh backend 100"
else
  ok "近期未见明显 error/traceback"
fi

echo ""
echo "----------------------------------------------"
echo -e "汇总：${GREEN}通过 ${PASS}${NC}  /  ${RED}失败 ${FAIL}${NC}"
echo "----------------------------------------------"

if [[ "${FAIL}" -gt 0 ]]; then
  echo ""
  warn "存在异常项，建议："
  echo "  ./logs.sh backend 100"
  echo "  ./logs.sh nginx-error"
  echo "  sudo systemctl status nginx ${SERVICE_NAME}"
  exit 1
fi

ok "全部检查通过"
exit 0
