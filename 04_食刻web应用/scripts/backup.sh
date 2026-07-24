#!/usr/bin/env bash
# =============================================================================
# 食刻 · 数据备份（稳住底盘）
# 安装位置建议：/opt/shike/backup.sh
# 用法：
#   ./backup.sh              # 立即备份
#   ./backup.sh --install-cron   # 安装每天 03:00 定时任务
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
SQLITE_DB="${DATA_DIR}/sqlite/recipes.db"
CHROMA_DIR="${DATA_DIR}/chroma"
BACKUP_ROOT="${SHIKE_ROOT}/backups"
KEEP_DAYS="${KEEP_DAYS:-7}"
MIN_FREE_GB="${MIN_FREE_GB:-1}"

# 可选远程：导出 OSS_BUCKET / EMAIL_TO 后启用
OSS_BUCKET="${OSS_BUCKET:-}"
EMAIL_TO="${EMAIL_TO:-}"

on_error() {
  local code=$?
  echo ""
  fail "备份失败（退出码 ${code}）。已创建的临时目录请人工检查: ${BACKUP_ROOT}"
}
trap on_error ERR

install_cron() {
  local script_path
  script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backup.sh"
  local line="0 3 * * * ${script_path} >> ${BACKUP_ROOT}/cron.log 2>&1"
  mkdir -p "${BACKUP_ROOT}"
  # 幂等：去掉旧的同脚本任务再添加
  local tmp
  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -vF "${script_path}" >"${tmp}" || true
  echo "${line}" >>"${tmp}"
  crontab "${tmp}"
  rm -f "${tmp}"
  ok "已安装定时任务：每天 03:00 执行"
  echo "  ${line}"
  crontab -l | grep -F "${script_path}" || true
  exit 0
}

if [[ "${1:-}" == "--install-cron" ]]; then
  install_cron
fi

echo "=============================================="
echo " 食刻 · 数据备份"
echo "=============================================="
echo ""

DATE_TAG="$(date +%F)"                 # 2026-07-24
STAMP="$(date +%Y%m%d_%H%M%S)"
DAY_DIR="${BACKUP_ROOT}/${DATE_TAG}"
ARCHIVE="${BACKUP_ROOT}/backup_${DATE_TAG}.tar.gz"
WORK_DIR="${DAY_DIR}_${STAMP}"

# --- 磁盘空间检查（可用 < 1GB 则报警退出）---
info "[1/7] 检查磁盘空间..."
avail_kb="$(df -Pk "${SHIKE_ROOT}" | awk 'NR==2{print $4}')"
avail_gb="$(awk -v k="${avail_kb}" 'BEGIN{printf "%.2f", k/1024/1024}')"
info "可用空间约 ${avail_gb} GB（阈值 ${MIN_FREE_GB} GB）"
if awk -v a="${avail_gb}" -v m="${MIN_FREE_GB}" 'BEGIN{exit !(a < m)}'; then
  fail "磁盘可用空间不足 ${MIN_FREE_GB}GB，请清理后再备份"
fi
ok "磁盘空间充足"

# --- 准备目录 ---
info "[2/7] 创建备份目录..."
mkdir -p "${WORK_DIR}"
ok "工作目录: ${WORK_DIR}"

# --- SQLite ---
info "[3/7] 备份 SQLite..."
if [[ ! -f "${SQLITE_DB}" ]]; then
  fail "找不到数据库: ${SQLITE_DB}"
fi
if command -v sqlite3 &>/dev/null; then
  sqlite3 "${SQLITE_DB}" ".backup ${WORK_DIR}/recipes_backup.db"
  sqlite3 "${SQLITE_DB}" ".dump" > "${WORK_DIR}/recipes_dump.sql"
  ok "SQLite .backup + .dump 完成"
else
  warn "未安装 sqlite3，改用文件复制"
  cp -a "${SQLITE_DB}" "${WORK_DIR}/recipes_backup.db"
  ok "已复制 recipes.db（建议: sudo apt-get install -y sqlite3）"
fi

# --- Chroma ---
info "[4/7] 备份 Chroma..."
if [[ -d "${CHROMA_DIR}" ]]; then
  tar -czf "${WORK_DIR}/chroma_backup.tar.gz" -C "${DATA_DIR}" chroma
  ok "Chroma 已打包: chroma_backup.tar.gz"
else
  warn "Chroma 目录不存在，跳过: ${CHROMA_DIR}"
fi

# --- 合并到按日目录并打总包 ---
info "[5/7] 整理并压缩当日备份..."
mkdir -p "${DAY_DIR}"
# 将本次产物同步进当日目录（可重复执行）
cp -a "${WORK_DIR}/." "${DAY_DIR}/"
# 打总包（覆盖同日归档，内容为最新一次）
tar -czf "${ARCHIVE}" -C "${BACKUP_ROOT}" "${DATE_TAG}"
ok "归档文件: ${ARCHIVE}"

# 清理本次临时工作目录（当日目录与 tar 已保留）
rm -rf "${WORK_DIR}"

# --- 清理过期 ---
info "[6/7] 清理 ${KEEP_DAYS} 天前的备份..."
# 删除过期日期目录
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"${KEEP_DAYS}" -print -exec rm -rf {} +
# 删除过期 tar
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'backup_20*.tar.gz' -mtime +"${KEEP_DAYS}" -print -delete
ok "保留策略: ${KEEP_DAYS} 天"

# --- 可选远程 ---
info "[7/7] 可选远程备份..."
if [[ -n "${OSS_BUCKET}" ]]; then
  if command -v ossutil &>/dev/null; then
    ossutil cp "${ARCHIVE}" "oss://${OSS_BUCKET}/shike-backups/$(basename "${ARCHIVE}")"
    ok "已上传 OSS: oss://${OSS_BUCKET}/shike-backups/$(basename "${ARCHIVE}")"
  elif command -v aliyun &>/dev/null; then
    warn "检测到 aliyun CLI，请自行配置 oss 上传；或安装 ossutil"
  else
    warn "已设置 OSS_BUCKET 但未找到 ossutil/aliyun，跳过上传"
  fi
else
  info "未设置 OSS_BUCKET，跳过 OSS"
fi

if [[ -n "${EMAIL_TO}" ]]; then
  if command -v mail &>/dev/null; then
    echo "食刻备份完成: ${ARCHIVE}" | mail -s "Shike backup ${DATE_TAG}" -A "${ARCHIVE}" "${EMAIL_TO}" \
      || warn "mail 发送失败（附件过大时常见），请改用 OSS"
    ok "已尝试发送邮件到 ${EMAIL_TO}"
  else
    warn "已设置 EMAIL_TO 但未找到 mail 命令，跳过"
  fi
else
  info "未设置 EMAIL_TO，跳过邮件"
fi

SIZE="$(du -h "${ARCHIVE}" | awk '{print $1}')"
echo ""
echo "=============================================="
ok "备份完成"
echo "  路径: ${ARCHIVE}"
echo "  大小: ${SIZE}"
echo "  明细目录: ${DAY_DIR}"
echo "=============================================="
