# 部署说明

## 1. 环境准备

```bash
cp .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY 和 AMAP_API_KEY
```

## 2. 数据初始化

```bash
cd backend
pip install -r requirements.txt
python -m pipeline.import_data --seed --count 3000
python -m pipeline.ingest --all
```

## 3. Docker 启动后端

```bash
# 在项目根目录
docker compose up -d --build
```

访问 http://localhost:8000/api/health 验证。

## 4. 前端开发

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## 5. 前端部署（Vercel）

1. 将 `frontend/` 目录连接到 Vercel
2. 设置环境变量 `VITE_API_BASE_URL` 为你的后端 API 地址
3. 修改 `vercel.json` 中的 API 反代地址
4. 执行 `npm run build` 部署

## 6. 生产环境 CORS

在 `.env` 或 docker-compose 中设置：

```
CORS_ORIGINS=https://your-frontend.vercel.app
```
