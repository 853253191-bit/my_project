#!/usr/bin/env bash
# =============================================================================
# 食刻 · 后端服务快捷管理
# 安装位置：/opt/shike/backend/backend.sh
# 用法：
#   ./backend.sh start|stop|restart|status|logs|test
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ️  $*${NC}"; }
ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
fail() { echo -e "${RED}❌ $*${NC}"; exit 1; }

SERVICE_NAME="${SERVICE_NAME:-shike-backend}"
# 健康检查路径为本项目实际接口 /api/health（不是 /health）
BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"
HEALTH_URL="${HEALTH_URL:-http://${BIND_HOST}:${BIND_PORT}/api/health}"

usage() {
  cat <<EOF
食刻后端管理脚本

用法:
  ./backend.sh start     启动服务
  ./backend.sh stop      停止服务
  ./backend.sh restart   重启服务
  ./backend.sh status    查看服务状态
  ./backend.sh logs      查看最近 50 行日志
  ./backend.sh test      本地测试 API 是否正常响应

环境变量（可选）:
  SERVICE_NAME=shike-backend
  BIND_HOST=127.0.0.1
  BIND_PORT=8000
EOF
}

require_service() {
  if ! systemctl list-unit-files "${SERVICE_NAME}.service" &>/dev/null; then
    fail "未找到 ${SERVICE_NAME}.service，请先执行 setup_backend.sh"
  fi
}

cmd_start() {
  require_service
  info "启动 ${SERVICE_NAME}..."
  sudo systemctl start "${SERVICE_NAME}"
  ok "已启动"
  sudo systemctl --no-pager --full status "${SERVICE_NAME}" | head -n 15 || true
}

cmd_stop() {
  require_service
  info "停止 ${SERVICE_NAME}..."
  sudo systemctl stop "${SERVICE_NAME}"
  ok "已停止"
}

cmd_restart() {
  require_service
  info "重启 ${SERVICE_NAME}..."
  sudo systemctl restart "${SERVICE_NAME}"
  sleep 1
  ok "已重启"
  sudo systemctl --no-pager --full status "${SERVICE_NAME}" | head -n 15 || true
}

cmd_status() {
  require_service
  sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true
  echo ""
  info "端口监听："
  if command -v ss &>/dev/null; then
    ss -tlnp | grep ":${BIND_PORT}" || warn "未检测到 ${BIND_PORT} 监听"
  else
    sudo netstat -tlnp 2>/dev/null | grep ":${BIND_PORT}" || warn "未检测到 ${BIND_PORT} 监听"
  fi
}

cmd_logs() {
  require_service
  info "最近 50 行日志（${SERVICE_NAME}）："
  sudo journalctl -u "${SERVICE_NAME}" -n 50 --no-pager
}

cmd_test() {
  info "请求 ${HEALTH_URL}"
  if curl -sf --max-time 5 "${HEALTH_URL}"; then
    echo ""
    ok "API 响应正常"
  else
    echo ""
    fail "API 无响应。查看日志: sudo journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
  fi
}

main() {
  case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    test)    cmd_test ;;
    -h|--help|"") usage ;;
    *) fail "未知命令: $1（使用 --help 查看用法）" ;;
  esac
}

main "$@"
