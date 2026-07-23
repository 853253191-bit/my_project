#!/usr/bin/env bash
# =============================================================================
# 食刻 Web 应用 — 服务器环境初始化脚本（第一阶段）
# 适用系统：Ubuntu 20.04 / 22.04 LTS
# 执行方式：以 root 运行  bash setup_server.sh
# =============================================================================

set -euo pipefail

# 遇到错误时打印信息并退出
on_error() {
  local exit_code=$?
  echo ""
  echo "❌ 脚本执行失败（退出码: ${exit_code}），请检查上方日志后重试。"
  exit "${exit_code}"
}
trap on_error ERR

echo "=============================================="
echo " 食刻 · 服务器环境初始化（第一阶段）"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# 0. 权限检查：必须以 root 执行
# -----------------------------------------------------------------------------
if [[ "$(id -u)" -ne 0 ]]; then
  echo "❌ 请使用 root 用户执行本脚本。"
  echo "   可先执行: sudo -i"
  echo "   再执行:   bash setup_server.sh"
  exit 1
fi
echo "✅ 已确认以 root 用户运行"
echo ""

# -----------------------------------------------------------------------------
# 1. 系统更新
# -----------------------------------------------------------------------------
echo ">>> [1/5] 更新系统软件包..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
echo "✅ 系统更新完成"
echo ""

# -----------------------------------------------------------------------------
# 2. 创建专用用户 deploy（幂等：已存在则跳过创建）
# -----------------------------------------------------------------------------
echo ">>> [2/5] 配置专用用户 deploy..."
DEPLOY_USER="deploy"

if id "${DEPLOY_USER}" &>/dev/null; then
  echo "ℹ️  用户 ${DEPLOY_USER} 已存在，跳过创建"
else
  # 创建可登录用户，并设置家目录
  adduser --disabled-password --gecos "Shike Deploy User" "${DEPLOY_USER}"
  echo "✅ 已创建用户 ${DEPLOY_USER}"
fi

# 确保加入 sudo 组（已在组内则无副作用）
usermod -aG sudo "${DEPLOY_USER}"
echo "✅ 用户 ${DEPLOY_USER} 已加入 sudo 组"

# 设置 / 更新登录密码（交互式输入，避免明文写在脚本里）
echo ""
echo "请为用户 ${DEPLOY_USER} 设置登录密码（输入时不显示）："
passwd "${DEPLOY_USER}"
echo "✅ 用户 ${DEPLOY_USER} 密码已设置"
echo ""

# -----------------------------------------------------------------------------
# 3. 安装必要软件（幂等：已安装则跳过）
# -----------------------------------------------------------------------------
echo ">>> [3/5] 安装必要软件..."

# 检查包是否已安装；未安装则加入待装列表
need_install=()
for pkg in git python3 python3-pip python3-venv python3-dev build-essential nginx; do
  if dpkg -s "${pkg}" &>/dev/null; then
    echo "ℹ️  ${pkg} 已安装，跳过"
  else
    need_install+=("${pkg}")
  fi
done

if [[ ${#need_install[@]} -gt 0 ]]; then
  echo "即将安装: ${need_install[*]}"
  apt-get install -y "${need_install[@]}"
else
  echo "ℹ️  所需软件均已安装，无需额外安装"
fi

# 确保 nginx 开机自启并处于运行状态
systemctl enable nginx
systemctl start nginx || systemctl restart nginx

echo "✅ 必要软件安装完成"
echo ""

# -----------------------------------------------------------------------------
# 4. 配置防火墙 UFW
# -----------------------------------------------------------------------------
echo ">>> [4/5] 配置防火墙..."

# 确保 ufw 已安装
if ! command -v ufw &>/dev/null; then
  apt-get install -y ufw
fi

# 开放必要端口（幂等：重复 allow 安全）
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp

# 非交互启用防火墙（已启用时再次执行也安全）
ufw --force enable

echo "✅ 防火墙配置完成"
echo ""

# -----------------------------------------------------------------------------
# 5. 验证安装
# -----------------------------------------------------------------------------
echo ">>> [5/5] 验证安装结果"
echo "----------------------------------------------"
echo -n "Python 版本:  "
python3 --version
echo -n "pip 版本:     "
pip3 --version
echo -n "Nginx 版本:   "
nginx -v 2>&1
echo "防火墙状态:"
ufw status
echo -n "当前登录用户: "
whoami
echo "----------------------------------------------"
echo ""
echo "✅ 第一阶段环境初始化全部完成"
echo ""
echo "后续建议："
echo "  1. 使用 deploy 用户登录:  ssh deploy@<服务器IP>"
echo "  2. 如需修改密码:         passwd"
echo "  3. 继续部署应用代码与 Nginx / SSL 配置（第二阶段）"
echo ""
