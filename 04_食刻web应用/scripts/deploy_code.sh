#!/usr/bin/env bash
# =============================================================================
# 食刻 Web 应用 — 代码部署与依赖安装（第二阶段）
# 适用：Ubuntu 20.04 / 22.04 LTS
# 执行用户：deploy（不要用 root）
# 用法：bash deploy_code.sh
# =============================================================================

set -euo pipefail

# -------------------------- 颜色与日志 --------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}ℹ️  $*${NC}"; }
ok()      { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${NC}"; }
fail()    { echo -e "${RED}❌ $*${NC}"; exit 1; }

on_error() {
  local code=$?
  echo ""
  fail "脚本执行失败（退出码: ${code}），请检查上方日志后重试。"
}
trap on_error ERR

# -------------------------- 可配置变量 --------------------------
SHIKE_ROOT="${SHIKE_ROOT:-/opt/shike}"
BACKEND_DIR="${SHIKE_ROOT}/backend"
FRONTEND_DIR="${SHIKE_ROOT}/frontend"
DATA_DIR="${SHIKE_ROOT}/data"
SQLITE_DIR="${DATA_DIR}/sqlite"
CHROMA_DIR="${DATA_DIR}/chroma"
VENV_DIR="${BACKEND_DIR}/venv"
ENV_FILE="${BACKEND_DIR}/.env"

# monorepo 中食刻子目录名（可通过环境变量覆盖）
SHIKE_SUBDIR="${SHIKE_SUBDIR:-04_食刻web应用}"

# Git 仓库（可用环境变量 SHIKE_GIT_URL 覆盖）
DEFAULT_GIT_URL="https://github.com/853253191-bit/my_project.git"
SHIKE_GIT_URL="${SHIKE_GIT_URL:-${DEFAULT_GIT_URL}}"
SHIKE_GIT_BRANCH="${SHIKE_GIT_BRANCH:-main}"

# 临时克隆目录
CLONE_DIR="${SHIKE_ROOT}/.src_repo"

echo "=============================================="
echo " 食刻 · 代码部署与依赖安装（第二阶段）"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# 0. 用户检查：禁止 root，建议 deploy
# -----------------------------------------------------------------------------
if [[ "$(id -u)" -eq 0 ]]; then
  fail "请使用 deploy 用户执行，不要使用 root。可执行: su - deploy"
fi

CURRENT_USER="$(whoami)"
if [[ "${CURRENT_USER}" != "deploy" ]]; then
  warn "当前用户是 ${CURRENT_USER}，推荐使用 deploy 用户。"
  read -r -p "是否继续？[y/N] " cont
  [[ "${cont}" =~ ^[Yy]$ ]] || fail "已取消"
fi
ok "当前用户: ${CURRENT_USER}"
echo ""

# 确保 rsync 可用（代码同步依赖）
if ! command -v rsync &>/dev/null; then
  info "安装 rsync..."
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y rsync
fi

# -----------------------------------------------------------------------------
# 1. 创建项目目录结构
# -----------------------------------------------------------------------------
info "[1/8] 创建项目目录结构..."
mkdir -p "${BACKEND_DIR}" "${FRONTEND_DIR}" "${SQLITE_DIR}" "${CHROMA_DIR}"
ok "目录结构已就绪: ${SHIKE_ROOT}"
echo ""

# -----------------------------------------------------------------------------
# 2. 设置目录权限
# -----------------------------------------------------------------------------
info "[2/8] 设置目录权限..."
# 若当前用户对 /opt/shike 无写权限，需要一次性 sudo 授权
if [[ ! -w "${SHIKE_ROOT}" ]]; then
  info "需要将 ${SHIKE_ROOT} 所有权交给 ${CURRENT_USER}（将请求 sudo）"
  sudo chown -R "${CURRENT_USER}:${CURRENT_USER}" "${SHIKE_ROOT}"
fi
chown -R "${CURRENT_USER}:${CURRENT_USER}" "${SHIKE_ROOT}"
find "${SHIKE_ROOT}" -type d -exec chmod 755 {} +
# 已有文件设为 644（跳过 venv 内可执行文件，后续重建）
find "${SHIKE_ROOT}" -type f ! -path '*/venv/*' -exec chmod 644 {} + 2>/dev/null || true
ok "目录权限设置完成（目录 755 / 文件 644）"
echo ""

# -----------------------------------------------------------------------------
# 3. 代码部署（Git Clone / SCP 二选一）
# -----------------------------------------------------------------------------
info "[3/8] 部署代码..."

sync_from_repo_tree() {
  # 从仓库树中同步 backend / frontend
  # 参数: $1 = 仓库根目录
  local repo_root="$1"
  local app_root=""

  if [[ -d "${repo_root}/${SHIKE_SUBDIR}/backend" ]]; then
    app_root="${repo_root}/${SHIKE_SUBDIR}"
  elif [[ -d "${repo_root}/backend" && -f "${repo_root}/backend/requirements.txt" ]]; then
    app_root="${repo_root}"
  else
    fail "未在仓库中找到 backend/requirements.txt（已尝试子目录: ${SHIKE_SUBDIR}）"
  fi

  info "从 ${app_root} 同步代码..."
  rsync -a --delete \
    --exclude 'venv/' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'node_modules/' \
    --exclude 'dist/' \
    "${app_root}/backend/" "${BACKEND_DIR}/"

  if [[ -d "${app_root}/frontend" ]]; then
    rsync -a --delete \
      --exclude 'node_modules/' \
      --exclude 'dist/' \
      "${app_root}/frontend/" "${FRONTEND_DIR}/"
  else
    warn "仓库中未找到 frontend 目录，跳过前端同步"
  fi
}

deploy_via_git() {
  info "方式 A：Git Clone / Pull"

  if [[ -d "${CLONE_DIR}/.git" ]]; then
    # 已存在：备份标记 + 拉取最新
    local bak="${SHIKE_ROOT}/.backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "${bak}"
    if [[ -f "${BACKEND_DIR}/requirements.txt" ]]; then
      cp -a "${BACKEND_DIR}" "${bak}/backend" 2>/dev/null || true
      ok "已备份当前 backend 到 ${bak}/backend"
    fi
    info "拉取最新代码 (${SHIKE_GIT_BRANCH})..."
    git -C "${CLONE_DIR}" fetch --all --prune
    git -C "${CLONE_DIR}" checkout "${SHIKE_GIT_BRANCH}"
    git -C "${CLONE_DIR}" pull --ff-only origin "${SHIKE_GIT_BRANCH}"
  else
    info "克隆仓库: ${SHIKE_GIT_URL}"
    rm -rf "${CLONE_DIR}"
    git clone --branch "${SHIKE_GIT_BRANCH}" --depth 1 "${SHIKE_GIT_URL}" "${CLONE_DIR}" \
      || git clone --depth 1 "${SHIKE_GIT_URL}" "${CLONE_DIR}"
  fi

  sync_from_repo_tree "${CLONE_DIR}"
  ok "Git 代码部署完成"
}

deploy_via_scp() {
  info "方式 B：SCP 上传（备选）"
  echo ""
  echo "请在【本地开发机】执行以下命令上传代码（请替换 SERVER_IP）："
  echo ""
  echo "  # 后端"
  echo "  scp -r ./backend/* deploy@SERVER_IP:${BACKEND_DIR}/"
  echo ""
  echo "  # 前端"
  echo "  scp -r ./frontend/* deploy@SERVER_IP:${FRONTEND_DIR}/"
  echo ""
  echo "  # （可选）SQLite 数据库"
  echo "  scp ./backend/data/sqlite/recipes.db deploy@SERVER_IP:${SQLITE_DIR}/recipes.db"
  echo ""
  echo "  # （可选）Chroma 向量库目录"
  echo "  scp -r ./backend/data/chroma deploy@SERVER_IP:${DATA_DIR}/"
  echo ""
  read -r -p "上传完成后按回车继续验证..." _

  if [[ ! -f "${BACKEND_DIR}/requirements.txt" ]]; then
    fail "未找到 ${BACKEND_DIR}/requirements.txt，请确认已正确上传后端代码"
  fi
  ok "SCP 代码完整性检查通过（requirements.txt 存在）"
}

echo "请选择代码部署方式："
echo "  1) Git Clone / Pull（推荐）"
echo "  2) SCP 上传（备选）"
read -r -p "输入 1 或 2 [默认 1]: " deploy_mode
deploy_mode="${deploy_mode:-1}"

case "${deploy_mode}" in
  2) deploy_via_scp ;;
  *) deploy_via_git ;;
esac

# 再次确保权限
chown -R "${CURRENT_USER}:${CURRENT_USER}" "${SHIKE_ROOT}"
echo ""

# -----------------------------------------------------------------------------
# 4. 创建 Python 虚拟环境
# -----------------------------------------------------------------------------
info "[4/8] 设置 Python 虚拟环境..."
if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
  ok "虚拟环境已创建: ${VENV_DIR}"
else
  info "虚拟环境已存在，跳过创建"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
ok "pip 已升级到最新版本"
echo ""

# -----------------------------------------------------------------------------
# 5. 安装 Python 依赖
# -----------------------------------------------------------------------------
info "[5/8] 安装 Python 依赖..."

if [[ ! -f "${BACKEND_DIR}/requirements.txt" ]]; then
  fail "缺少 ${BACKEND_DIR}/requirements.txt"
fi

install_python_deps() {
  pip install -r "${BACKEND_DIR}/requirements.txt"
  pip install "gunicorn" "uvicorn[standard]"
}

# 常见编译依赖（chromadb / 部分包可能需要）
ensure_build_deps() {
  warn "检测到可能缺少编译依赖，尝试安装系统包（需 sudo）..."
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential python3-dev libffi-dev libssl-dev \
    pkg-config cmake g++ || true
}

if ! install_python_deps; then
  warn "依赖安装失败，尝试补齐系统编译依赖后重试..."
  ensure_build_deps
  install_python_deps
fi
ok "Python 依赖安装完成（含 gunicorn / uvicorn[standard]）"
echo ""

# -----------------------------------------------------------------------------
# 6. 配置环境变量模板
# -----------------------------------------------------------------------------
info "[6/8] 配置环境变量..."
if [[ -f "${ENV_FILE}" ]]; then
  warn "${ENV_FILE} 已存在，保留现有文件（不覆盖）"
else
  cat > "${ENV_FILE}" <<EOF
# 食刻后端环境变量（请填入真实密钥，不要提交到 Git）
# DashScope / 通义（推荐）
DASHSCOPE_API_KEY=你的API密钥
AMAP_API_KEY=你的高德Key

# OpenAI 兼容接口（可指向 DashScope / DeepSeek / 官方 OpenAI）
OPENAI_API_KEY=你的API密钥
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-flash
OPENAI_EMBEDDING_MODEL=text-embedding-v3

# 数据路径（生产绝对路径）
DB_PATH=/opt/shike/data/sqlite/recipes.db
CHROMA_PATH=/opt/shike/data/chroma
# 兼容别名（部分文档写作 CHROMA_PERSIST_DIR，应用读取 CHROMA_PATH）
CHROMA_PERSIST_DIR=/opt/shike/data/chroma

# CORS（上线后改成你的前端域名，逗号分隔）
CORS_ORIGINS=http://localhost,http://127.0.0.1
EOF
  chmod 600 "${ENV_FILE}"
  ok "已创建环境变量模板: ${ENV_FILE}"
  warn "请立即编辑填入真实 API Key: nano ${ENV_FILE}"
fi
echo ""

# -----------------------------------------------------------------------------
# 7. 数据准备
# -----------------------------------------------------------------------------
info "[7/8] 准备数据目录..."
mkdir -p "${SQLITE_DIR}" "${CHROMA_DIR}"
chmod 755 "${SQLITE_DIR}" "${CHROMA_DIR}"

DB_FILE="${SQLITE_DIR}/recipes.db"
if [[ -f "${DB_FILE}" ]]; then
  ok "SQLite 数据库已存在: ${DB_FILE}"
else
  # 若代码自带 data/sqlite/recipes.db，尝试复制
  if [[ -f "${BACKEND_DIR}/data/sqlite/recipes.db" ]]; then
    cp -a "${BACKEND_DIR}/data/sqlite/recipes.db" "${DB_FILE}"
    ok "已从 backend 内置数据复制 recipes.db"
  else
    warn "未找到 ${DB_FILE}"
    echo ""
    echo "请从本地开发机上传数据库，例如："
    echo "  scp ./backend/data/sqlite/recipes.db deploy@$(hostname -I | awk '{print $1}'):${DB_FILE}"
    echo ""
    echo "上传 Chroma 向量库（若已有本地索引）："
    echo "  scp -r ./backend/data/chroma/* deploy@SERVER_IP:${CHROMA_DIR}/"
    echo ""
    warn "Chroma 数据须在后端服务启动前完成迁移；也可后续在服务器上执行 ingest 重建索引。"
  fi
fi
ok "Chroma 持久化目录就绪: ${CHROMA_DIR}"
echo ""

# -----------------------------------------------------------------------------
# 8. 验证安装
# -----------------------------------------------------------------------------
info "[8/8] 验证安装结果"
echo "----------------------------------------------"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
echo -n "Python 虚拟环境路径: "
which python3
echo ""
echo "关键包版本:"
pip list 2>/dev/null | grep -Ei "fastapi|uvicorn|chromadb|openai|gunicorn|dashscope" || warn "未匹配到关键包输出"
echo ""
echo "环境变量文件:"
ls -la "${ENV_FILE}" || warn ".env 不存在"
echo ""
echo "数据库文件:"
if [[ -f "${DB_FILE}" ]]; then
  ls -la "${DB_FILE}"
else
  warn "recipes.db 尚不存在，请按上方指引上传"
fi
echo ""
echo "Chroma 目录:"
ls -la "${CHROMA_DIR}"
echo "----------------------------------------------"
echo ""
ok "第二阶段代码部署与依赖安装流程结束"
echo ""
info "下一步建议："
echo "  1. 编辑密钥: nano ${ENV_FILE}"
echo "  2. 确认数据库已上传: ls -la ${DB_FILE}"
echo "  3. 使用快捷脚本: bash deploy.sh --status"
echo "  4. 后续阶段配置 systemd + Nginx 后再启动服务"
echo ""
