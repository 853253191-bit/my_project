#!/usr/bin/env bash
# =============================================================================
# 食刻 · Nginx 快捷管理
# 安装位置：/opt/shike/nginx.sh
# 用法：
#   ./nginx.sh status|restart|reload|config|logs
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

# 【手动修改】与 setup_frontend.sh 中 PUBLIC_HOST 保持一致
# 当前公网 IP：118.178.131.84
PUBLIC_HOST="${PUBLIC_HOST:-118.178.131.84}"
NGINX_AVAILABLE="${NGINX_AVAILABLE:-/etc/nginx/sites-available/shike}"
ACCESS_LOG="${ACCESS_LOG:-/var/log/nginx/access.log}"
ERROR_LOG="${ERROR_LOG:-/var/log/nginx/error.log}"

usage() {
  cat <<EOF
食刻 Nginx 管理脚本

用法:
  ./nginx.sh status    查看 Nginx 状态
  ./nginx.sh restart   重启 Nginx
  ./nginx.sh reload    重载 Nginx 配置（不中断连接）
  ./nginx.sh config    检查配置文件语法
  ./nginx.sh logs      查看访问日志（最近 20 行）

环境变量（可选）:
  PUBLIC_HOST=${PUBLIC_HOST}
  NGINX_AVAILABLE=${NGINX_AVAILABLE}
EOF
}

cmd_status() {
  sudo systemctl --no-pager --full status nginx || true
  echo ""
  info "端口监听："
  if command -v ss &>/dev/null; then
    ss -tlnp | grep -E ':80|:443' || warn "未检测到 80/443 监听"
  else
    sudo netstat -tlnp 2>/dev/null | grep -E ':80|:443' || warn "未检测到 80/443 监听"
  fi
  echo ""
  info "站点配置: ${NGINX_AVAILABLE}"
  info "公网地址: http://${PUBLIC_HOST}"
}

cmd_restart() {
  info "重启 Nginx..."
  sudo systemctl restart nginx
  ok "Nginx 已重启"
  systemctl is-active nginx
}

cmd_reload() {
  info "检查配置并重载..."
  sudo nginx -t
  sudo systemctl reload nginx
  ok "Nginx 配置已重载"
}

cmd_config() {
  info "检查 Nginx 配置语法..."
  sudo nginx -t
  ok "配置语法正确"
  echo ""
  if [[ -f "${NGINX_AVAILABLE}" ]]; then
    info "当前站点配置摘要（server_name / root / proxy）："
    grep -E '^\s*(server_name|root|proxy_pass|listen)' "${NGINX_AVAILABLE}" || true
  else
    warn "未找到 ${NGINX_AVAILABLE}"
  fi
}

cmd_logs() {
  info "访问日志最近 20 行（${ACCESS_LOG}）："
  if [[ -f "${ACCESS_LOG}" ]]; then
    sudo tail -n 20 "${ACCESS_LOG}"
  else
    warn "访问日志不存在: ${ACCESS_LOG}"
  fi
  echo ""
  info "错误日志最近 10 行（${ERROR_LOG}）："
  if [[ -f "${ERROR_LOG}" ]]; then
    sudo tail -n 10 "${ERROR_LOG}"
  else
    warn "错误日志不存在: ${ERROR_LOG}"
  fi
}

main() {
  case "${1:-}" in
    status)  cmd_status ;;
    restart) cmd_restart ;;
    reload)  cmd_reload ;;
    config)  cmd_config ;;
    logs)    cmd_logs ;;
    -h|--help|"") usage ;;
    *) fail "未知命令: $1（使用 --help 查看用法）" ;;
  esac
}

main "$@"
