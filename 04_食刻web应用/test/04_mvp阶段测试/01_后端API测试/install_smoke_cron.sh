#!/usr/bin/env bash
# 安装每日 04:00 冒烟测试 cron（需 root 或当前用户 crontab）
# 用法：bash install_smoke_cron.sh

set -euo pipefail

SHIKE_ROOT="${SHIKE_ROOT:-/opt/shike}"
BACKEND="${SHIKE_ROOT}/backend"
API_TEST="${SHIKE_ROOT}/test/04_mvp阶段测试/01_后端API测试"
LOG_DIR="${SHIKE_ROOT}/data/qa"
mkdir -p "${LOG_DIR}"

RUNNER="${LOG_DIR}/run_smoke_daily.sh"
cat > "${RUNNER}" <<EOF
#!/usr/bin/env bash
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin"
cd "${API_TEST}"
export ALERT_ON_FAIL=1
# 失败时由 run_tests.sh 调 alert.sh --smoke-failed
bash ./run_tests.sh --smoke >> "${LOG_DIR}/smoke_cron.log" 2>&1
CODE=\$?
if [[ "\${CODE}" -eq 0 ]]; then
  ALERT_RESET_SMOKE=1 bash "${BACKEND}/alert.sh" >/dev/null 2>&1 || true
fi
# 额外健康/磁盘巡检（运维脚本仍在 backend）
bash "${BACKEND}/alert.sh" --check-health --check-disk --check-recommend-latency >> "${LOG_DIR}/smoke_cron.log" 2>&1 || true
exit "\${CODE}"
EOF
chmod +x "${RUNNER}"

# 复制告警脚本到 /opt/shike/ 便于运维
if [[ -d "${SHIKE_ROOT}" ]]; then
  cp -f "${BACKEND}/alert.sh" "${SHIKE_ROOT}/alert.sh"
  chmod +x "${SHIKE_ROOT}/alert.sh" "${BACKEND}/alert.sh" "${API_TEST}/run_tests.sh" || true
fi

CRON_LINE="0 4 * * * ${RUNNER}"
( crontab -l 2>/dev/null | grep -v "run_smoke_daily.sh" || true; echo "${CRON_LINE}" ) | crontab -
echo "[OK] 已安装 cron: ${CRON_LINE}"
echo "[OK] 日志: ${LOG_DIR}/smoke_cron.log"
echo "[OK] 测试目录: ${API_TEST}"
