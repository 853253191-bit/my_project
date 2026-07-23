#!/usr/bin/env bash
# =============================================================================
# 食刻 · 快捷部署管理脚本
# 用法：
#   bash deploy.sh --update   # 拉取最新代码、更新依赖、重启服务
#   bash deploy.sh --status   # 检查当前服务状态
#   bash deploy.sh            # 显示帮助
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHIKE_ROOT="${SHIKE_ROOT:-/opt/shike}"
BACKEND_DIR="${SHIKE_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/venv"
CLONE_DIR="${SHIKE_ROOT}/.src_repo"
SHIKE_GIT_BRANCH="${SHIKE_GIT_BRANCH:-main}"

# systemd 服务名（第三阶段若未创建则仅提示）
BACKEND_SERVICE="${BACKEND_SERVICE:-shike-backend}"
NGINX_SERVICE="nginx"

usage() {
  cat <<EOF
食刻部署管理脚本

用法:
  bash deploy.sh --update    拉取最新代码，更新依赖，重启服务
  bash deploy.sh --status    检查当前服务 / 端口 / 关键文件状态
  bash deploy.sh --help      显示本帮助

环境变量（可选）:
  SHIKE_ROOT=/opt/shike
  SHIKE_GIT_URL=...
  SHIKE_GIT_BRANCH=main
  BACKEND_SERVICE=shike-backend
EOF
}

require_deploy_user() {
  if [[ "$(id -u)" -eq 0 ]]; then
    fail "请使用 deploy 用户执行，不要使用 root"
  fi
}

cmd_status() {
  echo "=============================================="
  echo " 食刻 · 服务状态"
  echo "=============================================="
  echo ""

  echo "--- 目录 ---"
  ls -ld "${SHIKE_ROOT}" "${BACKEND_DIR}" "${SHIKE_ROOT}/frontend" "${SHIKE_ROOT}/data" 2>/dev/null || warn "部分目录不存在"
  echo ""

  echo "--- 虚拟环境 ---"
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    "${VENV_DIR}/bin/python" --version
    ok "venv: ${VENV_DIR}"
  else
    warn "虚拟环境不存在: ${VENV_DIR}"
  fi
  echo ""

  echo "--- 环境变量 / 数据 ---"
  [[ -f "${BACKEND_DIR}/.env" ]] && ok ".env 存在" || warn ".env 不存在"
  [[ -f "${SHIKE_ROOT}/data/sqlite/recipes.db" ]] && ok "recipes.db 存在" || warn "recipes.db 不存在"
  [[ -d "${SHIKE_ROOT}/data/chroma" ]] && ok "chroma 目录存在" || warn "chroma 目录不存在"
  echo ""

  echo "--- 端口监听 ---"
  if command -v ss &>/dev/null; then
    ss -lntp | grep -E ':8000|:80|:443' || warn "未检测到 8000/80/443 监听"
  else
    netstat -lntp 2>/dev/null | grep -E ':8000|:80|:443' || warn "未检测到 8000/80/443 监听"
  fi
  echo ""

  echo "--- systemd ---"
  if systemctl list-unit-files "${BACKEND_SERVICE}.service" &>/dev/null; then
    systemctl --no-pager --full status "${BACKEND_SERVICE}.service" || true
  else
    warn "未找到 ${BACKEND_SERVICE}.service（可能尚未配置第三阶段 systemd）"
  fi
  echo ""
  if systemctl list-unit-files nginx.service &>/dev/null; then
    systemctl --no-pager --full status nginx.service | head -n 15 || true
  fi
  echo ""
}

cmd_update() {
  require_deploy_user
  echo "=============================================="
  echo " 食刻 · 更新部署"
  echo "=============================================="
  echo ""

  # 1) 拉取最新代码
  if [[ -d "${CLONE_DIR}/.git" ]]; then
    info "拉取最新代码..."
    git -C "${CLONE_DIR}" fetch --all --prune
    git -C "${CLONE_DIR}" checkout "${SHIKE_GIT_BRANCH}"
    git -C "${CLONE_DIR}" pull --ff-only origin "${SHIKE_GIT_BRANCH}" || \
      git -C "${CLONE_DIR}" pull --ff-only
    ok "代码已更新"
  else
    warn "未找到本地 Git 仓库 ${CLONE_DIR}"
    warn "将调用完整部署脚本（可选择 Git / SCP）"
    if [[ -f "${SCRIPT_DIR}/deploy_code.sh" ]]; then
      bash "${SCRIPT_DIR}/deploy_code.sh"
      return 0
    elif [[ -f "${SHIKE_ROOT}/scripts/deploy_code.sh" ]]; then
      bash "${SHIKE_ROOT}/scripts/deploy_code.sh"
      return 0
    else
      fail "找不到 deploy_code.sh，请先完成首次部署"
    fi
  fi

  # 2) 同步到 /opt/shike（复用 deploy_code 中的子目录逻辑）
  SHIKE_SUBDIR="${SHIKE_SUBDIR:-04_食刻web应用}"
  app_root=""
  if [[ -d "${CLONE_DIR}/${SHIKE_SUBDIR}/backend" ]]; then
    app_root="${CLONE_DIR}/${SHIKE_SUBDIR}"
  elif [[ -d "${CLONE_DIR}/backend" ]]; then
    app_root="${CLONE_DIR}"
  else
    fail "仓库结构异常，找不到 backend"
  fi

  info "同步 backend / frontend..."
  rsync -a --delete \
    --exclude 'venv/' --exclude '.venv/' --exclude '__pycache__/' \
    --exclude '*.pyc' --exclude '.env' \
    "${app_root}/backend/" "${BACKEND_DIR}/"
  if [[ -d "${app_root}/frontend" ]]; then
    rsync -a --delete \
      --exclude 'node_modules/' --exclude 'dist/' \
      "${app_root}/frontend/" "${SHIKE_ROOT}/frontend/"
  fi
  ok "代码同步完成"

  # 3) 更新依赖
  if [[ ! -x "${VENV_DIR}/bin/pip" ]]; then
    fail "虚拟环境不存在，请先执行 bash deploy_code.sh"
  fi
  info "更新 Python 依赖..."
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  pip install --upgrade pip
  pip install -r "${BACKEND_DIR}/requirements.txt"
  pip install "gunicorn" "uvicorn[standard]"
  ok "依赖更新完成"

  # 4) 重启服务
  info "尝试重启服务..."
  if systemctl list-unit-files "${BACKEND_SERVICE}.service" 2>/dev/null | grep -q "${BACKEND_SERVICE}"; then
    sudo systemctl restart "${BACKEND_SERVICE}.service"
    sudo systemctl restart "${NGINX_SERVICE}" || true
    ok "已重启 ${BACKEND_SERVICE} / ${NGINX_SERVICE}"
  else
    warn "未配置 ${BACKEND_SERVICE}.service，跳过重启"
    warn "可手动启动后端测试："
    echo "  cd ${BACKEND_DIR}"
    echo "  source venv/bin/activate"
    echo "  export PYTHONPATH=src"
    echo "  uvicorn shike.api.main:app --host 0.0.0.0 --port 8000"
  fi

  echo ""
  cmd_status
}

main() {
  local action="${1:-}"
  case "${action}" in
    --update|-u) cmd_update ;;
    --status|-s) cmd_status ;;
    --help|-h|"") usage ;;
    *)
      fail "未知参数: ${action}（使用 --help 查看用法）"
      ;;
  esac
}

main "$@"
