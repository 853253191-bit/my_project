# 食刻 · 服务器部署说明（第二阶段）

面向 Ubuntu 20.04 / 22.04 LTS，在已完成第一阶段（`setup_server.sh`）后执行。

## 目录约定

```text
/opt/shike/
├── backend/          # FastAPI 后端
│   ├── venv/         # Python 虚拟环境
│   └── .env          # 环境变量（勿提交 Git）
├── frontend/         # Vue 前端源码
├── data/
│   ├── sqlite/       # recipes.db
│   └── chroma/       # Chroma 持久化
└── .src_repo/        # Git 克隆缓存（方式 A）
```

## 首次部署步骤

### 1. 上传脚本到服务器

在本地（项目 `scripts/` 目录）：

```bash
scp setup_server.sh deploy_code.sh deploy.sh deploy@SERVER_IP:~/
```

或已用 Git 拉代码后，直接进入仓库内的 `04_食刻web应用/scripts/`。

### 2. 执行第二阶段

以 **deploy** 用户登录：

```bash
su - deploy
bash deploy_code.sh
```

按提示选择：

| 选项 | 说明 |
|------|------|
| `1` Git Clone | 默认从 monorepo 拉取，并同步 `04_食刻web应用` 下的 backend/frontend |
| `2` SCP 上传 | 按屏幕提示从本机 `scp` 上传，再回车继续 |

可选环境变量：

```bash
export SHIKE_GIT_URL=https://github.com/853253191-bit/my_project.git
export SHIKE_GIT_BRANCH=main
export SHIKE_SUBDIR=04_食刻web应用
bash deploy_code.sh
```

### 3. 填写密钥

```bash
nano /opt/shike/backend/.env
```

至少填写：

- `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`
- `AMAP_API_KEY`（天气相关）
- 确认 `DB_PATH`、`CHROMA_PATH` 指向 `/opt/shike/data/...`

### 4. 上传数据库（若脚本提示缺失）

```bash
# 在本地开发机
scp ./backend/data/sqlite/recipes.db deploy@SERVER_IP:/opt/shike/data/sqlite/recipes.db

# 若已有向量库（可选）
scp -r ./backend/data/chroma/* deploy@SERVER_IP:/opt/shike/data/chroma/
```

> Chroma 须在后端正式对外服务前迁移完成；也可后续在服务器上跑 ingest 重建。

### 5. 检查状态

```bash
bash deploy.sh --status
```

## 日常更新

```bash
bash deploy.sh --update
```

流程：`git pull` → 同步到 `/opt/shike` → 更新 pip 依赖 → 重启 `shike-backend` / nginx（若已配置 systemd）。

## 手动试跑后端（systemd 未就绪时）

```bash
cd /opt/shike/backend
source venv/bin/activate
export PYTHONPATH=src
uvicorn shike.api.main:app --host 127.0.0.1 --port 8000
```

另开终端：`curl http://127.0.0.1:8000/api/health`

## 常见问题

### 1. 提示没有 `/opt/shike` 写权限

首次可能需要：

```bash
sudo mkdir -p /opt/shike
sudo chown -R deploy:deploy /opt/shike
```

脚本在无写权限时也会尝试 `sudo chown`。

### 2. `pip install` 编译失败

脚本会自动尝试安装 `build-essential`、`python3-dev`、`libffi-dev` 等后重试。仍失败时手动：

```bash
sudo apt-get install -y build-essential python3-dev libffi-dev libssl-dev cmake pkg-config
source /opt/shike/backend/venv/bin/activate
pip install -r /opt/shike/backend/requirements.txt
```

### 3. Git 私有仓库认证失败

改用方式 B（SCP），或配置 deploy 用户的 SSH Deploy Key / Personal Access Token。

### 4. 找不到 `requirements.txt`

- Git 方式：确认仓库里存在 `04_食刻web应用/backend/requirements.txt`，或设置正确的 `SHIKE_SUBDIR`
- SCP 方式：确认上传的是 `backend/` 内容到 `/opt/shike/backend/`

### 5. `.env` 已存在不想被覆盖

脚本幂等：已有 `.env` **不会**覆盖，需手动编辑。

### 6. `--update` 提示没有 systemd 服务

属正常（第三阶段再配）。先用上文「手动试跑」验证，再配置 `shike-backend.service`。

## 相关脚本

| 文件 | 阶段 | 作用 |
|------|------|------|
| `setup_server.sh` | 一 | 系统更新、deploy 用户、基础软件、防火墙 |
| `deploy_code.sh` | 二 | 目录、代码、venv、依赖、`.env`、数据指引 |
| `deploy.sh` | 二+ | `--update` / `--status` 日常管理 |

## 安全提醒

- 全程使用 `deploy` 用户，避免 root 跑业务脚本
- API Key 只放在 `/opt/shike/backend/.env`，权限建议 `600`
- 不要把含真实密钥的 `.env` 提交到 Git
