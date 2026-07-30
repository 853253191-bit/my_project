#!/usr/bin/env bash
# =============================================================================
# 食刻 · 告警通知脚本
# 安装位置建议：/opt/shike/alert.sh （也可放 backend/alert.sh）
# 用法：
#   ./alert.sh --message "文本"
#   ./alert.sh --check-disk
#   ./alert.sh --check-health
#   ./alert.sh --check-recommend-latency
#   ./alert.sh --smoke-failed
# 环境变量（可写在 /opt/shike/backend/.env）：
#   ALERT_EMAIL / DINGTALK_WEBHOOK / FEISHU_WEBHOOK / WECOM_WEBHOOK
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

# 推断项目根与 backend（支持放在 backend/ 或 test/.../01_后端API测试/）
if [[ -d "${SCRIPT_DIR}/backend" ]]; then
  SHIKE_ROOT="${SCRIPT_DIR}"
  BACKEND_DIR="${SCRIPT_DIR}/backend"
elif [[ "$(basename "${SCRIPT_DIR}")" == "backend" ]]; then
  BACKEND_DIR="${SCRIPT_DIR}"
  SHIKE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [[ -d "${SCRIPT_DIR}/../../../backend" ]]; then
  # test/04_mvp阶段测试/01_后端API测试 → 项目根
  SHIKE_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
  BACKEND_DIR="${SHIKE_ROOT}/backend"
else
  SHIKE_ROOT="${SHIKE_ROOT:-/opt/shike}"
  BACKEND_DIR="${BACKEND_DIR:-${SHIKE_ROOT}/backend}"
fi

ENV_FILE="${BACKEND_DIR}/.env"
STATE_DIR="${SHIKE_ROOT}/data/qa"
mkdir -p "${STATE_DIR}"

# 加载 .env（简单 KEY=VAL）
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^(ALERT_|DINGTALK_|FEISHU_|WECOM_|TEST_|PREFERENCE_)' "${ENV_FILE}" | sed 's/\r$//' || true)
  set +a
fi

HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
RECOMMEND_URL="${RECOMMEND_URL:-http://127.0.0.1:8000/api/recommend}"
DISK_PATH="${DISK_PATH:-/opt/shike}"
DISK_THRESHOLD="${DISK_THRESHOLD:-85}"
SMOKE_FAIL_LIMIT="${SMOKE_FAIL_LIMIT:-3}"
LATENCY_MS_LIMIT="${LATENCY_MS_LIMIT:-3000}"
LATENCY_FAIL_LIMIT="${LATENCY_FAIL_LIMIT:-5}"

MSG=""
DO_DISK=0
DO_HEALTH=0
DO_LATENCY=0
DO_SMOKE_FAIL=0
DO_SEND_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message) MSG="${2:-}"; shift 2 ;;
    --check-disk) DO_DISK=1; shift ;;
    --check-health) DO_HEALTH=1; shift ;;
    --check-recommend-latency) DO_LATENCY=1; shift ;;
    --smoke-failed) DO_SMOKE_FAIL=1; shift ;;
    --send) DO_SEND_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# //;s/^#//'
      exit 0
      ;;
    *)
      warn "未知参数: $1"
      shift
      ;;
  esac
done

send_mail() {
  local subject="$1"
  local body="$2"
  if [[ -z "${ALERT_EMAIL:-}" ]]; then
    return 1
  fi
  if command -v mail >/dev/null 2>&1; then
    echo "${body}" | mail -s "${subject}" "${ALERT_EMAIL}" && return 0
  fi
  if command -v sendmail >/dev/null 2>&1; then
    {
      echo "To: ${ALERT_EMAIL}"
      echo "Subject: ${subject}"
      echo
      echo "${body}"
    } | sendmail -t && return 0
  fi
  return 1
}

send_dingtalk() {
  local text="$1"
  [[ -n "${DINGTALK_WEBHOOK:-}" ]] || return 1
  curl -sS -X POST "${DINGTALK_WEBHOOK}" \
    -H 'Content-Type: application/json' \
    -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"${text}\"}}" >/dev/null
}

send_feishu() {
  local text="$1"
  [[ -n "${FEISHU_WEBHOOK:-}" ]] || return 1
  curl -sS -X POST "${FEISHU_WEBHOOK}" \
    -H 'Content-Type: application/json' \
    -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"${text}\"}}" >/dev/null
}

send_wecom() {
  local text="$1"
  [[ -n "${WECOM_WEBHOOK:-}" ]] || return 1
  curl -sS -X POST "${WECOM_WEBHOOK}" \
    -H 'Content-Type: application/json' \
    -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"${text}\"}}" >/dev/null
}

notify_all() {
  local subject="$1"
  local body="$2"
  local text="[食刻告警] ${subject}\n${body}\n时间: $(date '+%Y-%m-%d %H:%M:%S')"
  local sent=0
  if send_mail "${subject}" "${body}"; then
    ok "邮件已发送 -> ${ALERT_EMAIL}"
    sent=1
  fi
  if send_dingtalk "${text}"; then
    ok "钉钉 Webhook 已发送"
    sent=1
  fi
  if send_feishu "${text}"; then
    ok "飞书 Webhook 已发送"
    sent=1
  fi
  if send_wecom "${text}"; then
    ok "企业微信 Webhook 已发送"
    sent=1
  fi
  if [[ "${sent}" -eq 0 ]]; then
    warn "未配置可用告警通道，仅写日志"
    echo "$(date -Iseconds) ${subject} | ${body}" >> "${STATE_DIR}/alert.log"
  fi
}

# ---------- 检查项 ----------
ALERTS=()

if [[ "${DO_DISK}" -eq 1 ]]; then
  usage="$(df -P "${DISK_PATH}" 2>/dev/null | awk 'NR==2{gsub(/%/,"",$5); print $5}')"
  usage="${usage:-0}"
  info "磁盘使用率 ${DISK_PATH}: ${usage}%"
  if [[ "${usage}" -ge "${DISK_THRESHOLD}" ]]; then
    ALERTS+=("磁盘使用率 ${usage}% >= ${DISK_THRESHOLD}%")
  else
    ok "磁盘正常"
  fi
fi

if [[ "${DO_HEALTH}" -eq 1 ]]; then
  code="$(curl -sS -o /tmp/shike_health.json -w '%{http_code}' --connect-timeout 5 --max-time 15 "${HEALTH_URL}" || echo 000)"
  info "health HTTP=${code}"
  if [[ "${code}" =~ ^5 ]] || [[ "${code}" == "000" ]]; then
    ALERTS+=("健康检查异常 HTTP=${code} url=${HEALTH_URL}")
  else
    ok "健康检查正常"
  fi
fi

if [[ "${DO_LATENCY}" -eq 1 ]]; then
  LAT_FILE="${STATE_DIR}/recommend_latency_fail.count"
  start_ns="$(date +%s%N)"
  code="$(curl -sS -o /tmp/shike_rec.json -w '%{http_code}' --connect-timeout 5 --max-time 20 \
    -H 'Content-Type: application/json' \
    -d '{"query_text":"随便吃点","filters":{},"top_k":1}' \
    "${RECOMMEND_URL}" || echo 000)"
  end_ns="$(date +%s%N)"
  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  info "recommend HTTP=${code} elapsed=${elapsed_ms}ms"
  count=0
  [[ -f "${LAT_FILE}" ]] && count="$(cat "${LAT_FILE}" 2>/dev/null || echo 0)"
  if [[ "${code}" != "200" ]] || [[ "${elapsed_ms}" -gt "${LATENCY_MS_LIMIT}" ]]; then
    count=$((count + 1))
    echo "${count}" > "${LAT_FILE}"
    warn "推荐延迟/失败计数=${count}"
    if [[ "${count}" -ge "${LATENCY_FAIL_LIMIT}" ]]; then
      ALERTS+=("推荐接口连续 ${count} 次超时或失败（>${LATENCY_MS_LIMIT}ms 或非200）最近=${elapsed_ms}ms")
      echo 0 > "${LAT_FILE}"
    fi
  else
    echo 0 > "${LAT_FILE}"
    ok "推荐延迟正常"
  fi
fi

if [[ "${DO_SMOKE_FAIL}" -eq 1 ]]; then
  SMOKE_FILE="${STATE_DIR}/smoke_fail.count"
  count=0
  [[ -f "${SMOKE_FILE}" ]] && count="$(cat "${SMOKE_FILE}" 2>/dev/null || echo 0)"
  count=$((count + 1))
  echo "${count}" > "${SMOKE_FILE}"
  warn "冒烟失败连续计数=${count}"
  if [[ "${count}" -ge "${SMOKE_FAIL_LIMIT}" ]]; then
    ALERTS+=("连续 ${count} 次冒烟测试失败")
    echo 0 > "${SMOKE_FILE}"
  fi
fi

# 冒烟成功时可手动清零：ALERT_RESET_SMOKE=1
if [[ "${ALERT_RESET_SMOKE:-0}" == "1" ]]; then
  echo 0 > "${STATE_DIR}/smoke_fail.count"
  ok "已重置冒烟失败计数"
fi

if [[ -n "${MSG}" ]]; then
  ALERTS+=("${MSG}")
fi

if [[ ${#ALERTS[@]} -eq 0 && "${DO_SEND_ONLY}" -eq 0 ]]; then
  ok "无告警触发"
  exit 0
fi

BODY="$(printf '%s\n' "${ALERTS[@]}")"
notify_all "食刻质量告警" "${BODY}"
exit 0
