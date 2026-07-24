#!/usr/bin/env bash
# =============================================================================
# 食刻 · 数据恢复（稳住底盘）
# 安装位置建议：/opt/shike/restore.sh
# 用法：
#   ./restore.sh /opt/shike/backups/backup_2026-07-24.tar.gz
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

SHIKE_ROOT="${SHIKE_ROOT:-/opt/shike}"
DATA_DIR="${SHIKE_ROOT}/data"
SQLITE_DIR="${DATA_DIR}/sqlite"
CHROMA_DIR="${DATA_DIR}/chroma"
SERVICE_NAME="${SERVICE_NAME:-shike-backend}"
RESTORE_TMP="${SHIKE_ROOT}/backups/.restore_tmp_$$"

usage() {
  cat <<EOF
食刻数据恢复

用法:
  ./restore.sh /opt/shike/backups/backup_YYYY-MM-DD.tar.gz

说明:
  - 恢复前会停止 ${SERVICE_NAME}
  - 恢复后会启动 ${SERVICE_NAME}
  - 默认会备份当前 data 到 data_before_restore_* 再覆盖
EOF
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" || -z "${1:-}" ]] && { usage; exit 0; }

ARCHIVE="$(readlink -f "$1" 2>/dev/null || realpath "$1" 2>/dev/null || echo "$1")"
[[ -f "${ARCHIVE}" ]] || fail "备份文件不存在: $1"

echo "=============================================="
echo " 食刻 · 数据恢复"
echo "=============================================="
echo ""
warn "即将从以下备份恢复（会覆盖现有 SQLite / Chroma）："
echo "  ${ARCHIVE}"
echo ""
read -r -p "确认继续？输入 YES 继续: " confirm
[[ "${confirm}" == "YES" ]] || fail "已取消恢复"

# --- 停止服务 ---
info "[1/6] 停止后端服务..."
sudo systemctl stop "${SERVICE_NAME}" || warn "停止服务时出现问题，继续尝试恢复"
ok "服务已停止（或本未运行）"

# --- 解压到临时目录 ---
info "[2/6] 解压备份包..."
rm -rf "${RESTORE_TMP}"
mkdir -p "${RESTORE_TMP}"
tar -xzf "${ARCHIVE}" -C "${RESTORE_TMP}"
# 兼容包内结构: backup_xxx.tar.gz 内含 2026-07-24/ 目录
DAY_DIR="$(find "${RESTORE_TMP}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
[[ -n "${DAY_DIR}" ]] || fail "备份包内未找到日期目录"
ok "解压目录: ${DAY_DIR}"

[[ -f "${DAY_DIR}/recipes_backup.db" ]] || fail "备份中缺少 recipes_backup.db"
[[ -f "${DAY_DIR}/chroma_backup.tar.gz" ]] || warn "备份中无 chroma_backup.tar.gz，将只恢复 SQLite"

# --- 保护现有数据 ---
info "[3/6] 备份当前数据（防误覆盖）..."
SAFETY="${SHIKE_ROOT}/backups/data_before_restore_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${SAFETY}"
if [[ -d "${DATA_DIR}" ]]; then
  # 若目标非空，先拷走
  if [[ -n "$(ls -A "${DATA_DIR}" 2>/dev/null || true)" ]]; then
    cp -a "${DATA_DIR}/." "${SAFETY}/"
    ok "当前 data 已复制到: ${SAFETY}"
  else
    info "data 目录为空，跳过安全拷贝"
  fi
else
  mkdir -p "${DATA_DIR}"
fi

# --- 恢复 SQLite ---
info "[4/6] 恢复 SQLite..."
mkdir -p "${SQLITE_DIR}"
cp -a "${DAY_DIR}/recipes_backup.db" "${SQLITE_DIR}/recipes.db"
chmod 644 "${SQLITE_DIR}/recipes.db"
ok "已恢复: ${SQLITE_DIR}/recipes.db"

# --- 恢复 Chroma ---
info "[5/6] 恢复 Chroma..."
if [[ -f "${DAY_DIR}/chroma_backup.tar.gz" ]]; then
  rm -rf "${CHROMA_DIR}"
  mkdir -p "${DATA_DIR}"
  tar -xzf "${DAY_DIR}/chroma_backup.tar.gz" -C "${DATA_DIR}"
  ok "已恢复: ${CHROMA_DIR}"
else
  warn "跳过 Chroma 恢复"
fi

rm -rf "${RESTORE_TMP}"

# --- 启动服务 ---
info "[6/6] 启动后端并做健康检查..."
sudo systemctl start "${SERVICE_NAME}"
sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}"; then
  ok "服务已启动"
else
  fail "服务启动失败，请: sudo journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
fi

code="$(curl -sS -o /tmp/shike_restore_health.txt -w "%{http_code}" --max-time 8 http://127.0.0.1/api/health 2>/dev/null || echo 000)"
if [[ "${code}" == "200" ]]; then
  ok "健康检查通过: $(cat /tmp/shike_restore_health.txt)"
else
  warn "健康检查 HTTP ${code}，请人工确认"
fi

echo ""
echo "=============================================="
ok "恢复流程结束"
echo "  安全副本: ${SAFETY}"
echo "  若异常可从安全副本手动拷回 data/"
echo "=============================================="
