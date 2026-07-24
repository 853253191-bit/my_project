#!/usr/bin/env bash
# =============================================================================
# 食刻 · 日志查看（稳住底盘）
# 安装位置建议：/opt/shike/logs.sh
# 用法：
#   ./logs.sh backend          # 实时跟踪后端日志
#   ./logs.sh backend 100      # 后端最近 100 行
#   ./logs.sh nginx            # Nginx 访问日志
#   ./logs.sh nginx-error      # Nginx 错误日志
#   ./logs.sh all              # 合并跟踪（后端 + Nginx）
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
ACCESS_LOG="${ACCESS_LOG:-/var/log/nginx/access.log}"
ERROR_LOG="${ERROR_LOG:-/var/log/nginx/error.log}"

usage() {
  cat <<EOF
食刻日志查看

用法:
  ./logs.sh backend [N]   后端日志（省略 N 则实时跟踪；有 N 则看最近 N 行，默认 50）
  ./logs.sh nginx         Nginx 访问日志（实时）
  ./logs.sh nginx-error   Nginx 错误日志（实时）
  ./logs.sh all           同时跟踪后端 + Nginx 访问/错误日志
  ./logs.sh help          显示帮助

环境变量:
  SERVICE_NAME=${SERVICE_NAME}
  ACCESS_LOG=${ACCESS_LOG}
  ERROR_LOG=${ERROR_LOG}
EOF
}

need_sudo_journal() {
  # journalctl 通常需要 sudo 才能看其它用户服务的全部日志
  if journalctl -u "${SERVICE_NAME}" -n 1 --no-pager &>/dev/null; then
    echo "journalctl"
  else
    echo "sudo journalctl"
  fi
}

cmd_backend() {
  local jc
  jc="$(need_sudo_journal)"
  if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
    local n="$1"
    info "后端最近 ${n} 行日志（${SERVICE_NAME}）"
    ${jc} -u "${SERVICE_NAME}" -n "${n}" --no-pager
  elif [[ -n "${1:-}" ]]; then
    fail "行数必须是数字，例如: ./logs.sh backend 100"
  else
    info "实时跟踪后端日志（Ctrl+C 退出）"
    ${jc} -u "${SERVICE_NAME}" -f
  fi
}

cmd_nginx() {
  [[ -f "${ACCESS_LOG}" ]] || fail "访问日志不存在: ${ACCESS_LOG}"
  info "实时跟踪 Nginx 访问日志（Ctrl+C 退出）"
  sudo tail -f "${ACCESS_LOG}"
}

cmd_nginx_error() {
  [[ -f "${ERROR_LOG}" ]] || fail "错误日志不存在: ${ERROR_LOG}"
  info "实时跟踪 Nginx 错误日志（Ctrl+C 退出）"
  sudo tail -f "${ERROR_LOG}"
}

cmd_all() {
  local jc
  jc="$(need_sudo_journal)"
  info "合并跟踪：后端 + Nginx access/error（Ctrl+C 退出）"
  warn "后端日志前缀 [backend]，Nginx 由 tail 输出"
  # 后台跟踪 journal，前台 tail 多个文件
  ${jc} -u "${SERVICE_NAME}" -f -o cat | sed -u 's/^/[backend] /' &
  local jpid=$!
  trap 'kill '"${jpid}"' 2>/dev/null || true; exit 0' INT TERM
  if [[ -f "${ACCESS_LOG}" ]] || [[ -f "${ERROR_LOG}" ]]; then
    files=()
    [[ -f "${ACCESS_LOG}" ]] && files+=("${ACCESS_LOG}")
    [[ -f "${ERROR_LOG}" ]] && files+=("${ERROR_LOG}")
    sudo tail -f "${files[@]}" || true
  else
    warn "Nginx 日志文件不存在，仅跟踪后端"
    wait "${jpid}"
  fi
}

main() {
  case "${1:-help}" in
    backend)      shift || true; cmd_backend "${1:-}" ;;
    nginx)        cmd_nginx ;;
    nginx-error)  cmd_nginx_error ;;
    all)          cmd_all ;;
    help|-h|--help) usage ;;
    *) fail "未知命令: $1（./logs.sh help）" ;;
  esac
}

main "$@"
