#!/usr/bin/env bash
# =============================================================================
# 食刻 Web 应用 — 前端部署与 Nginx 配置（第四阶段）
# 适用：Ubuntu 22.04 LTS
# 执行用户：deploy（需要 sudo）
# 用法：bash setup_frontend.sh
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

# -------------------------- 可配置项（更换域名/IP 时重点修改） --------------------------
# 【手动修改】公网访问地址（当前为阿里云 ECS 公网 IP）
# 后续若绑定域名，将 PUBLIC_HOST 改为 your.domain.com 即可
PUBLIC_HOST="${PUBLIC_HOST:-118.178.131.84}"

SHIKE_ROOT="${SHIKE_ROOT:-/opt/shike}"
FRONTEND_DIR="${SHIKE_ROOT}/frontend"
DIST_DIR="${FRONTEND_DIR}/dist"
BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-http://127.0.0.1:8000}"

NGINX_AVAILABLE="/etc/nginx/sites-available/shike"
NGINX_ENABLED="/etc/nginx/sites-enabled/shike"
NGINX_DEFAULT_ENABLED="/etc/nginx/sites-enabled/default"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo " 食刻 · 前端部署与 Nginx 配置（第四阶段）"
echo "=============================================="
echo ""
info "公网地址 PUBLIC_HOST = ${PUBLIC_HOST}"
info "静态目录 DIST_DIR     = ${DIST_DIR}"
info "后端上游 BACKEND      = ${BACKEND_UPSTREAM}"
echo ""

# -----------------------------------------------------------------------------
# 0. 前置检查
# -----------------------------------------------------------------------------
info "[0/6] 前置检查..."

if [[ "$(id -u)" -eq 0 ]]; then
  fail "请使用 deploy 用户执行，不要使用 root。可执行: su - deploy"
fi

CURRENT_USER="$(whoami)"
if [[ "${CURRENT_USER}" != "deploy" ]]; then
  warn "当前用户是 ${CURRENT_USER}，推荐使用 deploy"
  read -r -p "是否继续？[y/N] " cont
  [[ "${cont}" =~ ^[Yy]$ ]] || fail "已取消"
fi

if ! command -v nginx &>/dev/null; then
  fail "未检测到 nginx，请先完成第一阶段 setup_server.sh"
fi

ok "前置检查通过"
echo ""

# -----------------------------------------------------------------------------
# 1. 确认前端打包文件
# -----------------------------------------------------------------------------
info "[1/6] 确认前端打包文件..."

DIST_READY=0
if [[ -f "${DIST_DIR}/index.html" ]]; then
  DIST_READY=1
  ok "已找到前端打包文件: ${DIST_DIR}/index.html"
else
  warn "未找到 ${DIST_DIR}/index.html"
  echo ""
  echo "请按以下步骤准备前端静态文件："
  echo ""
  echo "  【方式 A】在本地开发机打包后上传："
  echo "    cd frontend"
  echo "    npm ci"
  echo "    npm run build"
  echo "    # 确保构建时 VITE_API_BASE_URL 为空或留空，走同源 /api 代理"
  echo "    scp -r dist deploy@${PUBLIC_HOST}:${DIST_DIR}"
  echo ""
  echo "  【方式 B】若服务器已有 Node.js，可在服务器上构建："
  echo "    cd ${FRONTEND_DIR}"
  echo "    npm ci && npm run build"
  echo ""
  read -r -p "上传/构建完成后按回车继续；若仍没有 dist 将跳过站点启用验证中的前端 HTML 检查: " _

  if [[ -f "${DIST_DIR}/index.html" ]]; then
    DIST_READY=1
    ok "已检测到前端打包文件"
  else
    warn "仍未检测到 dist，将继续写入 Nginx 配置，但首页访问会 404，直到你上传 dist"
  fi
fi

# 权限：Nginx 通常以 www-data 读静态文件
if [[ -d "${DIST_DIR}" ]]; then
  sudo chown -R deploy:deploy "${FRONTEND_DIR}"
  # 目录可遍历、文件可读
  find "${DIST_DIR}" -type d -exec chmod 755 {} + 2>/dev/null || true
  find "${DIST_DIR}" -type f -exec chmod 644 {} + 2>/dev/null || true
fi
echo ""

# -----------------------------------------------------------------------------
# 2. 创建 Nginx 站点配置
# -----------------------------------------------------------------------------
info "[2/6] 创建 Nginx 站点配置..."

NGINX_CONF=$(cat <<EOF
# 食刻 Nginx 站点配置
# 【手动修改】server_name：当前公网 IP = ${PUBLIC_HOST}
# 后续绑定域名时改为：server_name example.com www.example.com;
# 生成时间：$(date '+%Y-%m-%d %H:%M:%S')

server {
    listen 80;
    listen [::]:80;
    server_name ${PUBLIC_HOST};

    # 前端静态文件（Vue 打包产物）
    location / {
        root ${DIST_DIR};
        try_files \$uri \$uri/ /index.html;  # Vue Router history 模式
        index index.html;
    }

    # 后端 API 反向代理
    location /api/ {
        proxy_pass ${BACKEND_UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # API 文档（Swagger）
    location /docs {
        proxy_pass ${BACKEND_UPSTREAM}/docs;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # OpenAPI schema
    location /openapi.json {
        proxy_pass ${BACKEND_UPSTREAM}/openapi.json;
        proxy_set_header Host \$host;
    }

    # 可选：Swagger 静态资源
    location /redoc {
        proxy_pass ${BACKEND_UPSTREAM}/redoc;
        proxy_set_header Host \$host;
    }
}
EOF
)

if [[ -f "${NGINX_AVAILABLE}" ]]; then
  bak="${NGINX_AVAILABLE}.bak.$(date +%Y%m%d_%H%M%S)"
  sudo cp -a "${NGINX_AVAILABLE}" "${bak}"
  ok "已备份原配置到 ${bak}"
fi

echo "${NGINX_CONF}" | sudo tee "${NGINX_AVAILABLE}" >/dev/null
sudo chmod 644 "${NGINX_AVAILABLE}"
ok "Nginx 配置文件已创建: ${NGINX_AVAILABLE}"
echo ""

# -----------------------------------------------------------------------------
# 3. 启用站点并重启 Nginx
# -----------------------------------------------------------------------------
info "[3/6] 启用站点..."

# 禁用 default（若存在）
if [[ -L "${NGINX_DEFAULT_ENABLED}" ]] || [[ -f "${NGINX_DEFAULT_ENABLED}" ]]; then
  sudo rm -f "${NGINX_DEFAULT_ENABLED}"
  ok "已禁用默认站点 default"
fi

# 启用 shike（幂等：已存在软链接则不重复创建）
if [[ -L "${NGINX_ENABLED}" ]]; then
  current_target="$(readlink -f "${NGINX_ENABLED}" 2>/dev/null || true)"
  if [[ "${current_target}" == "$(readlink -f "${NGINX_AVAILABLE}")" ]]; then
    info "站点软链接已存在，跳过创建"
  else
    sudo rm -f "${NGINX_ENABLED}"
    sudo ln -s "${NGINX_AVAILABLE}" "${NGINX_ENABLED}"
    ok "已更新站点软链接"
  fi
elif [[ -e "${NGINX_ENABLED}" ]]; then
  warn "${NGINX_ENABLED} 已存在但不是软链接，先备份再替换"
  sudo mv "${NGINX_ENABLED}" "${NGINX_ENABLED}.bak.$(date +%Y%m%d_%H%M%S)"
  sudo ln -s "${NGINX_AVAILABLE}" "${NGINX_ENABLED}"
  ok "已创建站点软链接"
else
  sudo ln -s "${NGINX_AVAILABLE}" "${NGINX_ENABLED}"
  ok "已创建站点软链接: ${NGINX_ENABLED}"
fi

info "检查 Nginx 配置语法..."
if ! sudo nginx -t; then
  fail "Nginx 配置语法检查失败，请根据上方错误修正"
fi
ok "Nginx 配置语法检查通过"

sudo systemctl restart nginx
ok "Nginx 已重启"
echo ""

# -----------------------------------------------------------------------------
# 4. 验证部署
# -----------------------------------------------------------------------------
info "[4/6] 验证部署..."

if ! systemctl is-active --quiet nginx; then
  sudo systemctl status nginx --no-pager -l | head -n 30 || true
  fail "Nginx 未处于 running 状态"
fi
ok "Nginx 状态: active (running)"

echo "--- 80 端口 ---"
if command -v ss &>/dev/null; then
  ss -tlnp | grep ':80' || warn "未检测到 :80 监听"
else
  sudo netstat -tlnp 2>/dev/null | grep ':80' || warn "未检测到 :80 监听"
fi
echo ""

VERIFY_OK=1

echo "--- 本地首页 curl http://127.0.0.1 ---"
if [[ "${DIST_READY}" -eq 1 ]]; then
  if curl -sf --max-time 5 http://127.0.0.1/ | head -c 200 | grep -qi '<html\|<!doctype\|<title\|id="app"'; then
    ok "前端 HTML 响应正常"
  else
    warn "首页响应异常，请检查 ${DIST_DIR}"
    curl -sS --max-time 5 http://127.0.0.1/ | head -c 300 || true
    echo ""
    VERIFY_OK=0
  fi
else
  warn "跳过首页 HTML 检查（dist 尚未就绪）"
fi
echo ""

echo "--- API 代理 curl http://127.0.0.1/api/health ---"
if curl -sf --max-time 5 http://127.0.0.1/api/health; then
  echo ""
  ok "API 反向代理正常"
else
  echo ""
  warn "API 代理失败。请确认后端服务已启动："
  echo "  sudo systemctl status shike-backend"
  echo "  curl http://127.0.0.1:8000/api/health"
  VERIFY_OK=0
fi
echo ""

if [[ "${VERIFY_OK}" -ne 1 ]]; then
  warn "部分验证未通过，请按提示排查；Nginx 配置已写入"
fi

# -----------------------------------------------------------------------------
# 5. 安装便捷管理脚本
# -----------------------------------------------------------------------------
info "[5/6] 安装便捷管理脚本..."

NGINX_SH_SRC="${SCRIPT_DIR}/nginx.sh"
NGINX_SH_DST="${SHIKE_ROOT}/nginx.sh"

if [[ -f "${NGINX_SH_SRC}" ]]; then
  cp -a "${NGINX_SH_SRC}" "${NGINX_SH_DST}"
else
  fail "同目录缺少 nginx.sh 源文件: ${NGINX_SH_SRC}"
fi
chmod 755 "${NGINX_SH_DST}"
# 写入当前 PUBLIC_HOST，便于 logs/帮助信息展示
ok "快捷脚本已安装: ${NGINX_SH_DST}"
echo ""

# -----------------------------------------------------------------------------
# 6. 打印部署信息
# -----------------------------------------------------------------------------
info "[6/6] 汇总部署信息..."

NGINX_STATUS="$(systemctl is-active nginx 2>/dev/null || echo unknown)"

cat <<EOF

========================================
✅ 前端部署完成！

网站访问地址：  http://${PUBLIC_HOST}
API 文档地址：  http://${PUBLIC_HOST}/docs
后端健康检查：  http://${PUBLIC_HOST}/api/health

Nginx 状态：    ${NGINX_STATUS}
配置文件：      ${NGINX_AVAILABLE}
静态目录：      ${DIST_DIR}
公网 IP 标注：  ${PUBLIC_HOST}（更换域名时改 PUBLIC_HOST 后重跑本脚本）

常用命令：
  重启 Nginx    sudo systemctl restart nginx
  重载配置      sudo systemctl reload nginx
  查看状态      sudo systemctl status nginx
  查看访问日志  sudo tail -f /var/log/nginx/access.log
  查看错误日志  sudo tail -f /var/log/nginx/error.log

快捷脚本：
  ${NGINX_SH_DST} status|restart|reload|config|logs

⚠️ 注意：如果外网无法访问，请检查阿里云安全组是否放行 80 端口！
   同时确认本机 UFW 已允许 80/tcp（第一阶段应已配置）。
========================================
EOF
