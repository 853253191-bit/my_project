# 食刻 - 智能饮食决策 Web 应用

基于 LLM + RAG 的全栈食谱推荐系统：自然语言对话识别口味与场景，混合检索（SQLite + Chroma）推荐菜谱，并可生成详细做法。

- 前端：Vue 3 + Vite + Pinia
- 后端：FastAPI + Gunicorn/Uvicorn
- 数据：SQLite（结构化菜谱）+ Chroma（向量检索）
- 模型：通义 / DashScope OpenAI 兼容接口

## 项目结构

```text
04_食刻web应用/
├── backend/                 # FastAPI 后端
│   ├── src/shike/           # 应用代码
│   ├── pipeline/            # 导入 / 打标 / 向量迁移
│   ├── crawler/             # 菜谱爬虫
│   └── data/                # 本地数据（库文件默认不入库）
├── frontend/                # Vue 3 前端
├── scripts/                 # 服务器部署与验收脚本
├── spec/SPEC.md             # 规格说明
├── .env.example             # 环境变量模板
└── docker-compose.yml       # 可选 Docker 部署
```

## 本地开发

### 1. 环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```bash
DASHSCOPE_API_KEY=sk-你的真实密钥
OPENAI_API_KEY=                    # 可留空；若填写请用真实密钥，不要留「请填写」
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-flash
OPENAI_EMBEDDING_MODEL=text-embedding-v3
DB_PATH=data/sqlite/recipes.db
CHROMA_PATH=data/chroma
```

说明：后端会优先读取 `OPENAI_API_KEY`；若仍是占位符 `请填写`，会导致中文请求报错。建议与 `DASHSCOPE_API_KEY` 填同一密钥，或把 `OPENAI_API_KEY` 留空。

### 2. 后端

```bash
cd backend
python -m venv venv
# Windows PowerShell
.\venv\Scripts\Activate.ps1
# Linux / macOS
# source venv/bin/activate

pip install -r requirements.txt
set PYTHONPATH=src          # Windows CMD
# $env:PYTHONPATH="src"    # PowerShell
# export PYTHONPATH=src     # Linux / macOS

python -m shike.main
```

健康检查：http://127.0.0.1:8000/api/health  
接口文档：http://127.0.0.1:8000/docs

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

访问：http://localhost:5173  
开发环境通过 Vite 把 `/api` 代理到 `8000` 端口。

### 4. 数据与向量库

若本地已有 `backend/data/sqlite/recipes.db`，可直接使用。

首次推荐前需准备 Chroma 向量库（`chroma_count` 为 0 时会尝试自动迁移，生产环境建议先离线迁移）：

```bash
cd backend
# 确保已激活 venv，并加载 .env
python -m pipeline.migrate_to_vector_db --batch-size 50
```

爬虫采集（可选）：

```bash
cd backend
pip install -r crawler/requirements.txt
python -m crawler.run --site douguo --max 50
python -m pipeline.import_data --dir data/raw
```

## 生产部署（Ubuntu 22.04 / 阿里云 ECS）

推荐目录约定：

```text
/opt/shike/
├── backend/          # 代码 + venv + .env
├── frontend/dist/    # 前端打包产物
└── data/
    ├── sqlite/recipes.db
    └── chroma/
```

脚本位于 `scripts/`，按阶段执行（详见 [scripts/README_DEPLOY.md](scripts/README_DEPLOY.md)）：

| 阶段 | 脚本 | 作用 |
|------|------|------|
| 一 | `setup_server.sh` | 系统更新、deploy 用户、基础软件、防火墙 |
| 二 | `deploy_code.sh` / `deploy.sh` | 拉代码、venv、依赖、`.env` 模板 |
| 三 | `setup_backend.sh` / `backend.sh` | Gunicorn + systemd（`shike-backend`） |
| 四 | `setup_frontend.sh` / `nginx.sh` | 前端 `dist` + Nginx 反代 |
| 验收 | `verify_deploy.sh` | 服务 / 端口 / 健康检查 / 推荐接口 |

要点：

1. 后端仅监听 `127.0.0.1:8000`，由 Nginx 对外提供 `80`
2. systemd 建议设置 `LANG=C.UTF-8`、`PYTHONUTF8=1`
3. `OPENAI_API_KEY` 不要保留「请填写」
4. 上传真实 `recipes.db` 后，**先停服务再离线迁移 Chroma**，避免「readonly database」：

```bash
systemctl stop shike-backend
cd /opt/shike/backend && source venv/bin/activate
set -a && source .env && set +a
export PYTHONPATH=/opt/shike/backend/src
python -m pipeline.migrate_to_vector_db --batch-size 50
systemctl start shike-backend
curl -s http://127.0.0.1/api/health
```

5. 阿里云安全组需放行 **80/TCP**（HTTPS 另配 443）

常用运维：

```bash
systemctl status shike-backend nginx
journalctl -u shike-backend -f
curl -s http://127.0.0.1/api/health
curl -s -X POST http://127.0.0.1/api/parse_intent \
  -H "Content-Type: application/json" \
  -d '{"text":"今天想喝点热汤"}'
```

## Docker（可选）

```bash
cp .env.example .env
# 编辑密钥后
docker compose up -d --build
curl -s http://127.0.0.1:8000/api/health
```

## 相关文档

- [spec/SPEC.md](spec/SPEC.md) — 产品与技术规格
- [DEPLOY.md](DEPLOY.md) — 简要部署备忘
- [scripts/README_DEPLOY.md](scripts/README_DEPLOY.md) — 服务器分阶段部署说明
