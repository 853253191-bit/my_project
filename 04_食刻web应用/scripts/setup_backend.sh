#!/usr/bin/env bash
# =============================================================================
# 食刻 Web 应用 — 后端服务部署（第三阶段）
# 适用：Ubuntu 20.04 / 22.04 LTS
# 执行用户：deploy（需要 sudo 权限写 systemd）
# 用法：bash setup_backend.sh
# =============================================================================

set -euo pipefail

# -------------------------- 颜色与日志 --------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ️  $*${NC}"; }
ok()    { echo -e "${GREEN}✅ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $*${NC}"; }
fail()  { echo -e "${RED}❌ $*${NC}"; exit 1; }

on_error() {
  local code=$?
  echo ""
  fail "脚本执行失败（退出码: ${code}），请检查上方日志后重试。"
}
trap on_error ERR

# -------------------------- 可配置项（按需修改） --------------------------
# 【手动修改】Gunicorn 工作进程数
#   建议公式：2 * CPU核心数 + 1
#   内存 < 2GB 时建议改为 2
GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"

# 【手动修改】绑定地址（生产建议仅本机，由 Nginx 反代）
BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"

SHIKE_ROOT="${SHIKE_ROOT:-/opt/shike}"
BACKEND_DIR="${SHIKE_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/venv"
ENV_FILE="${BACKEND_DIR}/.env"
DATA_DIR="${SHIKE_ROOT}/data"
SQLITE_DIR="${DATA_DIR}/sqlite"
CHROMA_DIR="${DATA_DIR}/chroma"
SERVICE_NAME="shike-backend"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
# 模块路径：项目用 PYTHONPATH=src + shike.api.main:app（不是 src.shike...）
APP_MODULE="shike.api.main:app"
HEALTH_URL="http://${BIND_HOST}:${BIND_PORT}/api/health"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo " 食刻 · 后端服务部署（第三阶段）"
echo "=============================================="
echo ""
info "Gunicorn workers = ${GUNICORN_WORKERS}（可用环境变量 GUNICORN_WORKERS 覆盖）"
info "监听地址 = ${BIND_HOST}:${BIND_PORT}"
echo ""

# -----------------------------------------------------------------------------
# 0. 前置检查
# -----------------------------------------------------------------------------
info "[0/7] 前置检查..."

if [[ "$(id -u)" -eq 0 ]]; then
  fail "请使用 deploy 用户执行，不要使用 root。可执行: su - deploy"
fi

CURRENT_USER="$(whoami)"
if [[ "${CURRENT_USER}" != "deploy" ]]; then
  warn "当前用户是 ${CURRENT_USER}，推荐使用 deploy"
  read -r -p "是否继续？[y/N] " cont
  [[ "${cont}" =~ ^[Yy]$ ]] || fail "已取消"
fi

[[ -d "${BACKEND_DIR}" ]] || fail "后端目录不存在: ${BACKEND_DIR}（请先完成第二阶段）"
[[ -x "${VENV_DIR}/bin/gunicorn" ]] || fail "未找到 gunicorn，请先: source venv/bin/activate && pip install gunicorn 'uvicorn[standard]'"
[[ -f "${ENV_FILE}" ]] || fail "缺少环境变量文件: ${ENV_FILE}"
[[ -f "${BACKEND_DIR}/src/shike/api/main.py" ]] || fail "缺少应用入口: ${BACKEND_DIR}/src/shike/api/main.py"

# 确保数据目录存在（Chroma / SQLite）
mkdir -p "${SQLITE_DIR}" "${CHROMA_DIR}"
# 若 .env 写了 CHROMA_PATH / CHROMA_PERSIST_DIR，尽量创建
chroma_from_env="$(grep -E '^(CHROMA_PATH|CHROMA_PERSIST_DIR)=' "${ENV_FILE}" | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
if [[ -n "${chroma_from_env}" ]]; then
  mkdir -p "${chroma_from_env}"
fi

ok "前置检查通过"
echo ""

# -----------------------------------------------------------------------------
# 1. 测试 Gunicorn 启动（短暂探测后自动停止）
# -----------------------------------------------------------------------------
info "[1/7] 测试 Gunicorn 启动..."

cd "${BACKEND_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
export PYTHONPATH="${BACKEND_DIR}/src"
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

# 若 8000 已被占用，先提示
if ss -lntp 2>/dev/null | grep -q ":${BIND_PORT} " || netstat -lntp 2>/dev/null | grep -q ":${BIND_PORT} "; then
  if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    warn "端口 ${BIND_PORT} 已被 ${SERVICE_NAME} 占用，跳过临时启动测试（后续会重启服务）"
  else
    fail "端口 ${BIND_PORT} 已被占用，请先释放后再执行本脚本"
  fi
else
  TEST_LOG="$(mktemp /tmp/shike-gunicorn-test.XXXXXX.log)"
  info "后台短暂启动 Gunicorn 进行探测（约 8 秒）..."
  gunicorn -w "${GUNICORN_WORKERS}" -k uvicorn.workers.UvicornWorker \
    "${APP_MODULE}" --bind "${BIND_HOST}:${BIND_PORT}" \
    --access-logfile - --error-logfile - \
    >"${TEST_LOG}" 2>&1 &
  GUNI_PID=$!

  ready=0
  for i in $(seq 1 16); do
    if ! kill -0 "${GUNI_PID}" 2>/dev/null; then
      echo "----- Gunicorn 日志 -----"
      cat "${TEST_LOG}" || true
      fail "Gunicorn 进程意外退出，启动测试失败"
    fi
    if curl -sf --max-time 2 "${HEALTH_URL}" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 0.5
  done

  kill "${GUNI_PID}" 2>/dev/null || true
  wait "${GUNI_PID}" 2>/dev/null || true
  rm -f "${TEST_LOG}"

  if [[ "${ready}" -ne 1 ]]; then
    fail "Gunicorn 启动后未能在时限内响应 ${HEALTH_URL}"
  fi
  ok "Gunicorn 启动测试通过"
fi
echo ""

# -----------------------------------------------------------------------------
# 2. 创建 Systemd 服务文件（已存在则备份）
# -----------------------------------------------------------------------------
info "[2/7] 创建 Systemd 服务文件..."

SERVICE_CONTENT=$(cat <<EOF
[Unit]
Description=Shike FastAPI Backend Service
After=network.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=${BACKEND_DIR}
# 【手动修改】可按机器规格调整 -w 参数（当前: ${GUNICORN_WORKERS}）
Environment=PATH=${VENV_DIR}/bin
Environment=PYTHONPATH=${BACKEND_DIR}/src
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn -w ${GUNICORN_WORKERS} -k uvicorn.workers.UvicornWorker ${APP_MODULE} --bind ${BIND_HOST}:${BIND_PORT}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
)

if [[ -f "${SERVICE_FILE}" ]]; then
  bak="${SERVICE_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
  sudo cp -a "${SERVICE_FILE}" "${bak}"
  ok "已备份原服务文件到 ${bak}"
fi

echo "${SERVICE_CONTENT}" | sudo tee "${SERVICE_FILE}" >/dev/null
sudo chmod 644 "${SERVICE_FILE}"
ok "Systemd 服务文件已创建: ${SERVICE_FILE}"
echo ""

# -----------------------------------------------------------------------------
# 3. 配置目录与文件权限
# -----------------------------------------------------------------------------
info "[3/7] 配置服务权限..."

# 确保 /opt/shike 归属 deploy
if [[ -d "${SHIKE_ROOT}" ]]; then
  sudo chown -R deploy:deploy "${SHIKE_ROOT}"
fi

chmod 755 "${BACKEND_DIR}"
chmod 600 "${ENV_FILE}"
mkdir -p "${SQLITE_DIR}" "${CHROMA_DIR}"
chmod 755 "${DATA_DIR}" "${SQLITE_DIR}" "${CHROMA_DIR}"
[[ -f "${SQLITE_DIR}/recipes.db" ]] && chmod 644 "${SQLITE_DIR}/recipes.db" || true

ok "权限配置完成（.env=600，数据目录可写）"
echo ""

# -----------------------------------------------------------------------------
# 4. 启动并启用服务
# -----------------------------------------------------------------------------
info "[4/7] 启动并启用 Systemd 服务..."

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sleep 2

if ! sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
  warn "服务未处于 active，打印最近日志："
  sudo journalctl -u "${SERVICE_NAME}" -n 50 --no-pager || true
  fail "服务启动失败，请根据日志排查"
fi

ok "服务已启动并设置开机自启"
echo ""
info "服务状态摘要："
sudo systemctl status "${SERVICE_NAME}" --no-pager -l | head -n 20 || true
echo ""

# -----------------------------------------------------------------------------
# 5. 验证服务正常运行
# -----------------------------------------------------------------------------
info "[5/7] 验证服务正常运行..."

echo "--- 端口监听 ---"
if command -v ss &>/dev/null; then
  ss -tlnp | grep ":${BIND_PORT}" || warn "ss 未显示 ${BIND_PORT}（可能需稍等）"
else
  sudo netstat -tlnp | grep ":${BIND_PORT}" || warn "netstat 未显示 ${BIND_PORT}"
fi
echo ""

echo "--- 健康检查 ${HEALTH_URL} ---"
health_ok=0
for i in $(seq 1 10); do
  if curl -sf --max-time 3 "${HEALTH_URL}"; then
    echo ""
    health_ok=1
    break
  fi
  sleep 1
done

if [[ "${health_ok}" -ne 1 ]]; then
  warn "健康检查失败，最近 50 行日志："
  sudo journalctl -u "${SERVICE_NAME}" -n 50 --no-pager || true
  fail "API 未正常响应，请检查: sudo journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
fi
ok "健康检查通过"
echo ""

# -----------------------------------------------------------------------------
# 6. 安装便捷管理脚本 backend.sh
# -----------------------------------------------------------------------------
info "[6/7] 安装便捷管理脚本..."

BACKEND_SH_SRC="${SCRIPT_DIR}/backend.sh"
BACKEND_SH_DST="${BACKEND_DIR}/backend.sh"

if [[ -f "${BACKEND_SH_SRC}" ]]; then
  cp -a "${BACKEND_SH_SRC}" "${BACKEND_SH_DST}"
else
  # 若同目录无源文件，则内联写出一份
  cat > "${BACKEND_SH_DST}" <<'BACKEND_SH_EOF'
#!/usr/bin/env bash
# 食刻后端快捷管理（由 setup_backend.sh 安装）
set -euo pipefail
SERVICE_NAME="${SERVICE_NAME:-shike-backend}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
case "${1:-}" in
  start)   sudo systemctl start "${SERVICE_NAME}" ;;
  stop)    sudo systemctl stop "${SERVICE_NAME}" ;;
  restart) sudo systemctl restart "${SERVICE_NAME}" ;;
  status)  sudo systemctl status "${SERVICE_NAME}" --no-pager -l ;;
  logs)    sudo journalctl -u "${SERVICE_NAME}" -n 50 --no-pager ;;
  test)    curl -sS "${HEALTH_URL}"; echo ;;
  *) echo "用法: $0 {start|stop|restart|status|logs|test}"; exit 1 ;;
esac
BACKEND_SH_EOF
fi

chmod 755 "${BACKEND_SH_DST}"
ok "快捷脚本已安装: ${BACKEND_SH_DST}"
echo ""

# -----------------------------------------------------------------------------
# 7. 打印部署信息
# -----------------------------------------------------------------------------
info "[7/7] 汇总部署信息..."

STATUS_TEXT="$(systemctl is-active "${SERVICE_NAME}" 2>/dev/null || echo unknown)"
MAIN_PID="$(systemctl show -p MainPID --value "${SERVICE_NAME}" 2>/dev/null || echo unknown)"

cat <<EOF

========================================
✅ 后端服务部署完成！

服务状态：  ${STATUS_TEXT}
监听端口：  ${BIND_HOST}:${BIND_PORT}
进程 PID：  ${MAIN_PID}
工作进程：  ${GUNICORN_WORKERS}（可用 GUNICORN_WORKERS 调整后重跑本脚本）

常用命令：
  启动服务  sudo systemctl start ${SERVICE_NAME}
  停止服务  sudo systemctl stop ${SERVICE_NAME}
  重启服务  sudo systemctl restart ${SERVICE_NAME}
  查看状态  sudo systemctl status ${SERVICE_NAME}
  查看日志  sudo journalctl -u ${SERVICE_NAME} -f

快捷脚本：
  ${BACKEND_SH_DST} start|stop|restart|status|logs|test

测试命令：
  curl ${HEALTH_URL}

说明：
  - 服务仅绑定本机，由 Nginx 反向代理对外提供访问
  - 若推荐接口为空，请确认 Chroma 数据已迁移到 ${CHROMA_DIR}
========================================
EOF
