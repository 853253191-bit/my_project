#!/usr/bin/env bash
# =============================================================================
# 食刻 Web 应用 — 部署验证脚本（全流程验收）
# 适用：Ubuntu 22.04 LTS
# 执行用户：deploy
# 用法：bash verify_deploy.sh
# =============================================================================

set -uo pipefail
# 注意：不用 set -e，单步失败后继续跑完并汇总

# -------------------------- 颜色与日志 --------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ️  $*${NC}"; }
ok()    { echo -e "${GREEN}✅ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()   { echo -e "${RED}❌ $*${NC}"; }

# -------------------------- 可配置项 --------------------------
# 【手动修改】公网 IP（当前阿里云 ECS）
PUBLIC_HOST="${PUBLIC_HOST:-118.178.131.84}"

BACKEND_SERVICE="${BACKEND_SERVICE:-shike-backend}"
HEALTH_DIRECT="${HEALTH_DIRECT:-http://127.0.0.1:8000/api/health}"
HEALTH_PROXY="${HEALTH_PROXY:-http://127.0.0.1/api/health}"
FRONT_URL="${FRONT_URL:-http://127.0.0.1/}"
RECOMMEND_URL="${RECOMMEND_URL:-http://127.0.0.1/api/recommend}"
TEST_QUERY="${TEST_QUERY:-今天好累，想喝点热汤}"

PASS=0
FAIL=0
WARN_COUNT=0

# 报告字段
R_NGINX="❌ 未检测"
R_BACKEND="❌ 未检测"
R_PORT80="❌ 未监听"
R_PORT8000="❌ 未监听"
R_HEALTH="❌ 失败"
R_PROXY="❌ 失败"
R_FRONT="❌ 失败"
R_RECOMMEND="❌ 失败"
R_SAMPLE_TITLE=""
R_SAMPLE_SUMMARY=""
R_SAMPLE_TIME=""
R_SAMPLE_DIFF=""
R_HEALTH_BODY=""
R_RECOMMEND_COUNT=0

pass() {
  PASS=$((PASS + 1))
  ok "$1"
}

fail_step() {
  FAIL=$((FAIL + 1))
  err "$1"
}

warn_step() {
  WARN_COUNT=$((WARN_COUNT + 1))
  warn "$1"
}

echo "=============================================="
echo " 食刻 · 部署验证"
echo "=============================================="
echo ""
info "公网地址: http://${PUBLIC_HOST}"
info "测试查询: ${TEST_QUERY}"
echo ""

# -----------------------------------------------------------------------------
# 1. 检查服务状态
# -----------------------------------------------------------------------------
info "[1/9] 检查服务状态..."

NGINX_STATE="$(systemctl is-active nginx 2>/dev/null || echo inactive)"
BACKEND_STATE="$(systemctl is-active "${BACKEND_SERVICE}" 2>/dev/null || echo inactive)"

if [[ "${NGINX_STATE}" == "active" ]]; then
  R_NGINX="✅ active (running)"
  pass "Nginx：active (running)"
else
  R_NGINX="❌ ${NGINX_STATE}"
  fail_step "Nginx 未运行（状态: ${NGINX_STATE}）"
fi

if [[ "${BACKEND_STATE}" == "active" ]]; then
  R_BACKEND="✅ active (running)"
  pass "后端服务 ${BACKEND_SERVICE}：active (running)"
else
  R_BACKEND="❌ ${BACKEND_STATE}"
  fail_step "后端服务未运行（状态: ${BACKEND_STATE}）"
  warn_step "排查: sudo systemctl status ${BACKEND_SERVICE}"
  warn_step "日志: sudo journalctl -u ${BACKEND_SERVICE} -n 50 --no-pager"
fi
echo ""

# -----------------------------------------------------------------------------
# 2. 检查端口监听
# -----------------------------------------------------------------------------
info "[2/9] 检查端口监听..."

ss_out="$(ss -tlnp 2>/dev/null || true)"

if echo "${ss_out}" | grep -qE ':80\s'; then
  R_PORT80="✅ 已监听"
  pass "80 端口（HTTP）已监听"
  echo "${ss_out}" | grep -E ':80\s' || true
else
  R_PORT80="❌ 未监听"
  fail_step "80 端口未监听"
fi

if echo "${ss_out}" | grep -qE ':8000\s'; then
  R_PORT8000="✅ 已监听"
  pass "8000 端口（API）已监听"
  echo "${ss_out}" | grep -E ':8000\s' || true
else
  R_PORT8000="❌ 未监听"
  fail_step "8000 端口未监听"
fi
echo ""

# -----------------------------------------------------------------------------
# 3. 测试本地 API 健康检查（直连后端）
# -----------------------------------------------------------------------------
info "[3/9] 测试本地 API 健康检查（${HEALTH_DIRECT}）..."

health_direct_body="$(curl -sS --max-time 8 "${HEALTH_DIRECT}" 2>/dev/null || true)"
if [[ -n "${health_direct_body}" ]] && echo "${health_direct_body}" | grep -qi '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  R_HEALTH="✅ 通过"
  R_HEALTH_BODY="${health_direct_body}"
  pass "直连健康检查通过"
  echo "  响应: ${health_direct_body}"
else
  R_HEALTH="❌ 失败"
  fail_step "直连健康检查失败或超时"
  [[ -n "${health_direct_body}" ]] && echo "  响应: ${health_direct_body}"
fi
echo ""

# -----------------------------------------------------------------------------
# 4. 测试本地 API 代理（经 Nginx）
# -----------------------------------------------------------------------------
info "[4/9] 测试 Nginx API 代理（${HEALTH_PROXY}）..."

health_proxy_body="$(curl -sS --max-time 8 "${HEALTH_PROXY}" 2>/dev/null || true)"
if [[ -n "${health_proxy_body}" ]] && echo "${health_proxy_body}" | grep -qi '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  R_PROXY="✅ 通过"
  pass "Nginx API 代理通过"
  echo "  响应: ${health_proxy_body}"
else
  R_PROXY="❌ 失败"
  fail_step "Nginx API 代理失败（请检查 /etc/nginx/sites-available/shike 中 location /api/）"
  [[ -n "${health_proxy_body}" ]] && echo "  响应: ${health_proxy_body}"
fi
echo ""

# -----------------------------------------------------------------------------
# 5. 测试前端页面可访问性
# -----------------------------------------------------------------------------
info "[5/9] 测试前端页面（${FRONT_URL}）..."

front_code="$(curl -sS -o /tmp/shike_front_check.html -w "%{http_code}" --max-time 8 "${FRONT_URL}" 2>/dev/null || echo "000")"
if [[ "${front_code}" == "200" ]]; then
  R_FRONT="✅ 通过 (HTTP 200)"
  pass "前端页面可访问（HTTP 200）"
else
  R_FRONT="❌ 失败 (HTTP ${front_code})"
  fail_step "前端页面异常（HTTP ${front_code}），请检查 /opt/shike/frontend/dist 与 Nginx root 配置"
fi
echo ""

# -----------------------------------------------------------------------------
# 6. 测试核心推荐功能
# -----------------------------------------------------------------------------
info "[6/9] 测试推荐接口（query: ${TEST_QUERY}）..."

recommend_body="$(curl -sS --max-time 60 -X POST "${RECOMMEND_URL}" \
  -H "Content-Type: application/json" \
  -d "{\"query_text\":\"${TEST_QUERY}\",\"filters\":{},\"top_k\":1}" 2>/dev/null || true)"

if [[ -z "${recommend_body}" ]]; then
  R_RECOMMEND="❌ 失败（无响应）"
  fail_step "推荐接口无响应或超时"
else
  # 解析 count / 首条字段（优先 python3，回退 grep）
  parse_ok=0
  if command -v python3 &>/dev/null; then
    parsed="$(printf '%s' "${recommend_body}" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("ERR")
    raise SystemExit(0)
items = data.get("items") or []
count = data.get("count", len(items))
print(count)
if items:
    it = items[0]
    print(it.get("title") or "")
    print((it.get("decision_summary") or "").replace("\n", " "))
    t = it.get("estimated_time")
    print("" if t is None else t)
    print(it.get("ai_difficulty") or "")
else:
    print("")
    print("")
    print("")
    print("")
' 2>/dev/null || echo "ERR")"

    if [[ "${parsed}" != "ERR" && -n "${parsed}" ]]; then
      mapfile -t lines <<< "${parsed}"
      R_RECOMMEND_COUNT="${lines[0]:-0}"
      R_SAMPLE_TITLE="${lines[1]:-}"
      R_SAMPLE_SUMMARY="${lines[2]:-}"
      R_SAMPLE_TIME="${lines[3]:-}"
      R_SAMPLE_DIFF="${lines[4]:-}"
      parse_ok=1
    fi
  fi

  if [[ "${parse_ok}" -eq 1 ]]; then
    if [[ "${R_RECOMMEND_COUNT}" =~ ^[0-9]+$ ]] && [[ "${R_RECOMMEND_COUNT}" -gt 0 ]] && [[ -n "${R_SAMPLE_TITLE}" ]]; then
      R_RECOMMEND="✅ 通过 (返回 ${R_RECOMMEND_COUNT} 条结果)"
      pass "推荐接口通过（返回 ${R_RECOMMEND_COUNT} 条）"
      echo "  菜名: ${R_SAMPLE_TITLE}"
    else
      R_RECOMMEND="❌ 空结果"
      fail_step "推荐接口返回空结果，可能 Chroma 未迁移或不完整"
      echo "  响应摘要: $(printf '%s' "${recommend_body}" | head -c 300)"
    fi
  else
    if echo "${recommend_body}" | grep -q '"items"[[:space:]]*:[[:space:]]*\[' \
      && ! echo "${recommend_body}" | grep -q '"items"[[:space:]]*:[[:space:]]*\[\]'; then
      R_RECOMMEND="✅ 通过（含 items）"
      pass "推荐接口有返回 items（未能精细解析字段）"
    else
      R_RECOMMEND="❌ 失败"
      fail_step "推荐接口响应异常"
      echo "  响应: $(printf '%s' "${recommend_body}" | head -c 400)"
    fi
  fi
fi
echo ""

# -----------------------------------------------------------------------------
# 7. 公网访问提示（可选）
# -----------------------------------------------------------------------------
info "[7/9] 公网访问提示..."
echo "  请在浏览器打开: http://${PUBLIC_HOST}"
echo "  若外网无法访问，请检查阿里云安全组是否放行 80 端口，以及 UFW 是否允许 80/tcp。"

# 可选：从本机探测公网（可能因安全策略失败，仅警告）
public_code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 8 "http://${PUBLIC_HOST}/" 2>/dev/null || echo "000")"
if [[ "${public_code}" == "200" ]]; then
  pass "公网首页探测成功（HTTP 200）"
else
  warn_step "公网探测返回 HTTP ${public_code}（若你在服务器本机测也可能受策略影响，请以浏览器为准）"
fi
echo ""

# -----------------------------------------------------------------------------
# 8. 检查错误日志
# -----------------------------------------------------------------------------
info "[8/9] 检查错误日志..."

backend_err="$(sudo journalctl -u "${BACKEND_SERVICE}" -n 50 --no-pager 2>/dev/null | grep -iE 'error|traceback|exception' | tail -n 5 || true)"
if [[ -n "${backend_err}" ]]; then
  warn_step "后端日志中发现可能的错误（最近匹配）："
  echo "${backend_err}"
  warn_step "完整日志: sudo journalctl -u ${BACKEND_SERVICE} -n 100 --no-pager"
else
  pass "后端近期日志未见明显 error/traceback"
fi

nginx_err="$(sudo tail -n 50 /var/log/nginx/error.log 2>/dev/null | grep -i error | tail -n 5 || true)"
if [[ -n "${nginx_err}" ]]; then
  warn_step "Nginx 错误日志中有记录："
  echo "${nginx_err}"
  warn_step "查看: sudo tail -f /var/log/nginx/error.log"
else
  pass "Nginx 错误日志未见明显 error"
fi
echo ""

# -----------------------------------------------------------------------------
# 9. 生成验证报告
# -----------------------------------------------------------------------------
info "[9/9] 生成验证报告..."

# 耗时展示
time_label=""
if [[ -n "${R_SAMPLE_TIME}" ]]; then
  time_label="${R_SAMPLE_TIME}分钟"
else
  time_label="—"
fi
diff_label="${R_SAMPLE_DIFF:-—}"

ALL_CORE_PASS=0
if [[ "${FAIL}" -eq 0 ]]; then
  ALL_CORE_PASS=1
fi

cat <<EOF

========================================
✅ 部署验证完成！

【服务状态】
  Nginx：        ${R_NGINX}
  后端服务：     ${R_BACKEND}

【端口监听】
  80 (HTTP)：    ${R_PORT80}
  8000 (API)：   ${R_PORT8000}

【功能测试】
  健康检查：      ${R_HEALTH}
  API 代理：      ${R_PROXY}
  前端页面：      ${R_FRONT}
  推荐接口：      ${R_RECOMMEND}

【外网访问】
  访问地址：      http://${PUBLIC_HOST}
  建议操作：      在浏览器中打开确认页面正常

【测试样例】
  推荐结果示例：
  - 菜名：    ${R_SAMPLE_TITLE:-（无）}
  - 摘要：    ${R_SAMPLE_SUMMARY:-（无）}
  - 耗时：    ${time_label}
  - 难度：    ${diff_label}

【统计】
  通过：${PASS}    失败：${FAIL}    警告：${WARN_COUNT}
========================================
EOF

if [[ "${ALL_CORE_PASS}" -eq 1 ]]; then
  cat <<EOF
✅ 所有测试通过！系统已就绪，可正式使用。

⚠️  后续建议：
  1. 配置 SSL 证书启用 HTTPS（Let's Encrypt）
  2. 购买域名并绑定到服务器
  3. 定期备份 SQLite 数据库和 Chroma 向量库
========================================
EOF
  exit 0
else
  cat <<EOF
❌ 存在失败项，请根据上方日志排查后再验收。

常用排查命令：
  sudo systemctl status nginx ${BACKEND_SERVICE}
  sudo journalctl -u ${BACKEND_SERVICE} -n 50 --no-pager
  sudo nginx -t && sudo tail -50 /var/log/nginx/error.log
  curl -s http://127.0.0.1:8000/api/health
  curl -s http://127.0.0.1/api/health
========================================
EOF
  exit 1
fi
