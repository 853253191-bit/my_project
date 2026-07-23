# 食刻 - 智能饮食决策 Web 应用

基于 LLM + RAG 的全栈食谱推荐系统。

## 爬虫采集

```bash
cd backend
pip install -r crawler/requirements.txt

# 豆果美食（API，无需浏览器）
python -m crawler.run --site douguo --max 50

# 美食天下（分类分页 + 多 worker；建议 3~5）
python -m crawler.run --site meishichina --max 5000 --workers 5 --category-pages 25

# 导入爬取结果到 SQLite
python -m pipeline.import_data --dir data/raw
python -m pipeline.ingest --all
```

输出文件：
- `backend/data/raw/douguo_recipes.json`
- `backend/data/raw/meishichina_recipes.json`


```bash
# 1. 配置环境变量
cp .env.example .env

# 2. 初始化数据
cd backend
pip install -r requirements.txt
python -m pipeline.import_data --seed
python -m pipeline.ingest --all

# 3. 启动后端
python -m shike.main

# 4. 启动前端（新终端）
cd frontend
npm install
npm run dev
```

## 项目结构

- `spec/SPEC.md` - 完整规格文档
- `backend/` - FastAPI 后端 + 数据流水线
- `frontend/` - Vue 3 前端
- `docker-compose.yml` - Docker 部署配置

详细部署说明见 [DEPLOY.md](DEPLOY.md)。
