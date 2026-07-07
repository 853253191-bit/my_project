# Manus 产业链投研 Agent

面向 **AI 产业硬件链** 的逆向 BOM 投研流水线。系统按 **单步执行 + 人工确认** 模式运行：每个 Agent 完成后暂停，在网页端展示结构化结果；满意则进入下一步，不满意则重跑当前步。最终由 Agent6 汇总前五步输出，生成 Markdown 研究报告。

详细产品规格见 [`docs/SPEC.md`](docs/SPEC.md)。

---

## 功能概览

| Step | Agent | 职责 |
|------|-------|------|
| 0 | Agent1 NewsCollector | 采集近 24h AI 硬件向热点新闻 Top5（美股/A 股产业链新技术与热门方向） |
| 1 | Agent2 ComponentMapper | 基于选定新闻拆解产业链 BOM，评估终端需求 outlook |
| 2 | Agent3 BottleneckAnalyzer | 识别产业链瓶颈；无结果时回退为 Agent2 产业链环节 |
| 3 | Agent4 QuantValidator | 断供测试、定量验证、Red-team；BOM 回退模式下预匹配 A 股标的 |
| 4 | Agent5 SupplierScreener | **A 股沪深主板**供应商筛选（Tushare 检索 + LLM 推荐 + 财务摘要） |
| 5 | Agent6 ReportWriter | 生成十章节 Markdown 报告并落盘 |

**方法论来源**：[`knowledge/strategy.txt`](knowledge/strategy.txt)，通过 Chroma 向量 RAG 在各 Agent 节点按需检索注入。

**交互模式**：FastAPI + SSE 实时进度；每步 `awaiting_step_approval` 等待用户 `proceed` / `rerun` / `change_direction`。

---

## 环境要求

- Python **3.11+**
- Windows / Linux / macOS

---

## 快速开始

### 1. 安装依赖

```powershell
cd "D:\myproject\02_langgraph_agent助手\my_manus"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置文件

复制示例配置并填写密钥：

```powershell
copy config\config.example.toml config\config.toml
```

或在环境变量中设置（推荐，避免密钥写入文件）：

| 变量 | 用途 |
|------|------|
| `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` | 大模型（Qwen / OpenAI 兼容接口） |
| `TAVILY_API_KEY` | Agent1 新闻检索 |
| `TUSHARE_TOKEN` / `TUSHARE_API_KEY` | Agent4/5 A 股匹配与财务查询 |
| `MANUS_RUNS_DIR` | 可选，run 状态持久化目录，默认 `runs/` |

Embedding 默认复用 LLM 的 `api_key` 与 `base_url`（DashScope `text-embedding-v3`）。

### 3. 构建 RAG 知识库（首次使用建议执行）

```powershell
$env:PYTHONPATH = "src"

# 策略库（knowledge/strategy.txt）
python -m manus.rag.ingest --collection strategy

# 案例库（Web_Crawler/output/aleabitoreddit/汇总2.md，若存在）
python -m manus.rag.ingest --collection cases
```

向量库写入 `src/manus/rag/store/`（已在 `.gitignore` 中忽略）。

### 4. 启动 Web 服务

```powershell
$env:PYTHONPATH = "src"
python -m manus.main
```

浏览器打开：**http://127.0.0.1:5173**

健康检查：`GET /health` 应返回 `{"status":"ok","version":"0.1.1"}`。

> 修改代码后需**重启服务**，否则仍运行旧逻辑。

---

## Web 端使用流程

1. 首页点击 **「开始采集」** → 创建 run，后台执行 Agent1，SSE 实时展示进度。
2. Step0 确认面板展示 Top5 新闻 → 选择一条 → **「满意，下一步」**（需传 `news_id`）。
3. Step1～5 依次确认 Agent2～6 的输出；不满意可 **「重跑本步」**。
4. Agent3 瓶颈不足时，确认面板可能提示 `suggest_deepen_bom`；Step2 重跑可自动加深 BOM。
5. 完成后报告写入 `output/reports/`，run 目录下另有 `runs/{run_id}/report.md`。

### 确认动作说明

| action | 含义 |
|--------|------|
| `proceed` | 满意，进入下一步 Agent |
| `rerun` | 重跑当前 Agent（按 SPEC 清除下游字段） |
| `change_direction` | Step1 换新闻方向；Step3 换瓶颈研究方向 |

---

## CLI 用法

```powershell
$env:PYTHONPATH = "src"

# 创建 run
python -m manus.cli run create

# 列出历史 run
python -m manus.cli run list --limit 10

# 查看某步状态
python -m manus.cli run step-view --run-id run-xxx --step 0

# 确认 / 重跑（与 API resolve 等价）
python -m manus.cli run resolve --run-id run-xxx --step 0 --action proceed --news-id news-001
```

CLI 与 FastAPI 共用同一套 `PipelineRunner` / `RunManager`。

---

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/runs` | 创建 run，后台跑 Agent1 |
| GET | `/runs/{id}/events` | SSE 事件流（进度、LLM 流式输出） |
| GET | `/runs/{id}` | 完整 PipelineState JSON |
| GET | `/runs/{id}/steps/{step}` | 当前待确认步骤的输出视图 |
| POST | `/runs/{id}/steps/{step}/resolve` | `proceed` / `rerun` / `change_direction` |
| POST | `/runs/{id}/rerun?from=N` | 兼容旧版重跑接口 |

---

## 项目结构

```
my_manus/
├── config/
│   └── config.example.toml    # 配置模板（复制为 config.toml）
├── docs/
│   ├── SPEC.md                # 完整产品规格
│   └── TODOLIST.md
├── knowledge/
│   └── strategy.txt           # 投研策略知识库源文件
├── src/manus/
│   ├── api/                   # FastAPI、RunManager、SSE
│   ├── pipeline/              # 状态机、Runner、门控、BOM 加深/回退
│   ├── steps/                 # Agent1～6 实现
│   ├── tools/                 # 新闻搜索、Tushare、供应商筛选
│   ├── rag/                   # Chroma 检索与 ingest
│   ├── schemas/               # Pydantic 模型
│   ├── main.py                # uvicorn 入口
│   └── cli.py                 # 命令行入口
├── static/                    # 前端 JS/CSS
├── templates/                 # index.html
├── runs/                      # 每次 run 的 state.json（运行时生成）
├── output/reports/            # Agent6 报告输出
├── tests/                     # pytest 测试套件
└── requirements.txt
```

---

## Agent5 A 股匹配说明

- **数据源**：Tushare Pro（公司名 / 行业 / 概念板块成分股）。
- **范围**：仅 **沪深主板**（600/601/603/605/000/001/002），排除科创板 688、创业板 300、北交所及 ST。
- **合并逻辑**：Tushare 结构化候选 + Agent4 预匹配 + LLM 推荐 → 字段归一化 → 主板过滤 → Tushare 财务摘要。
- 新闻中常见的创业板龙头（如中际旭创 300308）会被过滤；系统会优先返回主板相关标的（如光迅科技 002281、长电科技 600584 等）。

---

## 运行测试

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/ -q
```

---

## 常见问题

**Q：页面报错 `'dict' object has no attribute 'model_dump'`**  
A：多为旧服务未重启。结束占用 5173 端口的进程后重新 `python -m manus.main`，确认 `/health` 含 `version`。

**Q：A 股匹配为空**  
A：检查 `TUSHARE_TOKEN` 是否配置；查看 run 的 `state.json` 中 `errors` 字段（如 `tushare_no_match`、`supplier_skip_*`）。Agent3 无瓶颈时会走 BOM 回退，建议在 Step2 重跑加深 BOM。

**Q：报告大量「（待补充）」**  
A：Agent6 LLM 生成失败时会用结构化模板兜底；上游 Agent2/3/5 产出不完整时模板只能填少量字段。可对 Step5 重跑或检查 LLM API。

**Q：RAG 检索为空**  
A：执行 `python -m manus.rag.ingest` 构建向量库；未 ingest 时会降级为 fallback 策略片段。

---

## 免责声明

本系统输出为 **研究辅助**，不构成投资建议。报告固定附带免责声明；最终投资决策须人工复核。

---

## 相关文档

- [产品规格说明书（SPEC）](docs/SPEC.md)
- [开发任务清单（TODOLIST）](docs/TODOLIST.md)
