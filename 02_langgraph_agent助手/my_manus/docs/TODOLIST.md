# Manus 实现待办清单（TODOLIST）

| 属性 | 值 |
|------|-----|
| 对应规格 | [SPEC.md](./SPEC.md) **v1.4.1** |
| 项目路径 | `02_langgraph_agent助手/my_manus/` |
| 当前代码状态 | **尚无 `app/`**，从 P0 开始 |
| 更新日期 | 2026-07-07 |

本文档将 SPEC 拆解为可执行的开发任务，按 **P0 → P4** 顺序推进。完成一项后将 `[ ]` 改为 `[x]`。

---

## 0. 实现前必读（硬约定）

实现代码前请确认以下约定，避免与 SPEC 冲突：

| 约定 | 说明 |
|------|------|
| step 编号 | **0～5** 唯一体系；`agent = step + 1`（step0=Agent1 … step5=Agent6） |
| 确认 API | `POST /runs/{run_id}/steps/{step}/resolve`，**不存在 step6** |
| 编排 | **Python Pipeline + RunManager**，不使用 LangGraph |
| 逐步确认 | 默认 `step_approval_required=true`；每 Agent 后 `awaiting_step_approval` |
| Agent5 标的 | 仅 **A 股沪深主板**；688/300/北交所/ST 由 `supplier_screen` 硬过滤 |
| Schema | Pydantic 模型与 SPEC **附录 A** 1:1 对齐 |

```text
step0 Agent1 → 确认 → step1 Agent2 → … → step5 Agent6 → completed
```

---

## 1. 环境与工程骨架（P0 前置）

### 1.1 依赖与配置

- [ ] 创建 `requirements.txt`（对齐 SPEC §9.1）
- [ ] 创建 `config/config.example.toml`（对齐 SPEC §7.1：`llm` / `search` / `rag` / `workflow` / `finance` / `supplier_screen` / `output`）
- [ ] 实现 `app/config.py`：加载 `config.toml`，支持环境变量 Fallback（§7.2）
- [ ] 添加 `.gitignore` 条目：`config/config.toml`、`app/rag/store/`、`runs/`、`output/reports/`（§7.3）
- [ ] 创建空目录：`app/`、`config/`、`templates/`、`static/`、`output/reports/`、`runs/`

### 1.2 基础模块

- [ ] `app/llm.py`：OpenAI-compatible 封装（chat + JSON mode）
- [ ] `app/schemas/`：按附录 A 定义 Pydantic 模型（见 §2.1 清单）
- [ ] `app/prompts/`：各 Agent 的 system/user 模板占位文件

**验收**：`python -c "from app.config import load_config; load_config()"` 不报错（无 config 时给出明确提示）。

---

## 2. P0 — RAG 基础

**目标**：`strategy.txt` 可向量检索，供各 Agent 按章节注入。

| 文件 | SPEC 章节 |
|------|-----------|
| `app/rag/ingest.py` | §5.2 |
| `app/rag/retriever.py` | §5.3、§5.4 |
| `app/rag/store/` | Chroma 持久化 |

### 2.1 任务清单

- [ ] `ingest.py`：按 `##` / `###` 切分 `knowledge/strategy.txt`，metadata 含 `section_id`、`title`
- [ ] 支持 CLI：`python -m app.rag.ingest --source knowledge/strategy.txt`
- [ ] `retriever.py`：按 Agent 名 + semantic query 检索（§5.4 对照表）
- [ ] 实现 `top_k`、`score_threshold`、`max_context_chars` 配置项
- [ ] RAG 为空时注入 fallback 片段并写 `errors[]`（§5.5）
- [ ] （可选 P4 预研）第二 corpus `汇总2.md` 的 ingest 接口预留

### 2.2 验收标准

- [ ] `ingest` 后 Chroma 中有 strategy 分块
- [ ] 对 Agent2 的 query 模板返回 top-5，单条 chunk 可包装为 `=== 策略知识库 ===` 格式
- [ ] Windows 10 + Python 3.11 下可重复执行 ingest

---

## 3. P1 — Pipeline 与 CLI（核心工作流）

**目标**：无 UI 情况下，CLI 完成「单步执行 + 逐步确认 + resolve」全链路。

### 3.1 PipelineState 与持久化

- [ ] `app/pipeline/state.py`：`PipelineState`（§3.1 字段表，含 `pending_approval_step`、`approval_hints`、`suppliers_excluded` 等）
- [ ] `RunManager` 持久化：`runs/{run_id}/state.json`、`runs/{run_id}/run.log`（§8.3）
- [ ] 实现字段清除矩阵（§3.2.5）：`rerun` / `change_direction` 时按 step 清空下游字段

### 3.2 门控

- [ ] `app/pipeline/gates.py`：`gate_outlook`（§3.2.1）→ `approval_hints`
- [ ] `gate_checklist`（§3.2.2）→ `checklist_gate` + `approval_hints`
- [ ] Agent4 内 `gate_checklist_auto_retry` 一次（§7.1 `workflow.gate_checklist_auto_retry`）

### 3.3 PipelineRunner

- [ ] `app/pipeline/runner.py`：`run_single_step(run_id, step)`，step **0～5**
- [ ] `resolve_step(run_id, step, action, news_id?)`：`proceed` / `rerun` / `change_direction`
- [ ] 每步结束：`status=awaiting_step_approval`，SSE 事件占位（先 log 即可）
- [ ] 降级逻辑（§3.3）：失败 → `approval_hints.degraded=true`，**不自动 proceed**
- [ ] `step_approval_required=false` 时连续执行（§3.2 全自动模式说明）
- [ ] Agent3：`bottleneck < 2` 时设 `approval_hints.suggest_deepen_bom`（§4.3），不自动 deepen

### 3.4 六 Agent 步骤（最小可跑通）

每个 step 文件：RAG 检索 → LLM structured output → 写 state → 调门控。

| step | 文件 | SPEC |
|------|------|------|
| 0 | `steps/agent1_news.py` | §4.1 |
| 1 | `steps/agent2_components.py` | §4.2 |
| 2 | `steps/agent3_bottleneck.py` | §4.3 |
| 3 | `steps/agent4_quant.py` | §4.4（含 red_team 子步骤） |
| 4 | `steps/agent5_supplier.py` | §4.5（初版可先不做 finance 硬过滤） |
| 5 | `steps/agent6_report.py` | §4.6（初版可先内存 Markdown，不落盘） |

- [ ] Agent1：`search_news` + `rss_fetch` + `dedupe_and_rank`（`app/tools/`）
- [ ] Agent2：输出 `component_node` + `horizontal_branches`
- [ ] Agent3：输出 `bottlenecks` + `ripple_notes`
- [ ] Agent4：输出 `validations` + `red_team`
- [ ] Agent5：输出 `suppliers`（P1 可用 mock 或跳过硬过滤）
- [ ] Agent6：输出 `final_report_md`（P1 可用简单模板）

### 3.5 工具层（P1 最小集）

- [ ] `app/tools/search_news.py`：Tavily / Serper / Bing 适配（§4.1）
- [ ] `app/tools/rss_fetch.py`
- [ ] `app/tools/web_search.py`（Agent3/4 可选）
- [ ] `app/tools/python_execute.py`（Agent4 定量，§4.4）

### 3.6 CLI（§6.6）

- [ ] `app/cli.py` 或 `python -m app.cli`：
  - `run create --run-date`
  - `run step-view --run-id --step`
  - `run resolve --run-id --step --action [--news-id]`
  - `run list --limit`
- [ ] CLI 与未来将实现的 `RunManager` 共用同一套 `PipelineRunner`

### 3.7 P1 验收标准

- [ ] CLI 创建 run → Agent1 完成 → `pending_approval_step=0`
- [ ] `resolve proceed --news-id` → 逐步执行至 step5 或中途 `rerun` 当前步
- [ ] `change_direction`（step1）回到 step0
- [ ] `gate_outlook stop` 时 `block_proceed=true`
- [ ] 全程 `runs/{run_id}/state.json` 可恢复状态
- [ ] 重复 `proceed` 同 step 返回逻辑等价 409（Runner 层校验）

---

## 4. P2 — Web 端（FastAPI + SSE）

**目标**：浏览器完成与 CLI 等价的逐步确认体验。

### 4.1 后端 API

- [ ] `app/main.py`：FastAPI 入口，`127.0.0.1`（§9）
- [ ] `POST /runs`（§6.2）
- [ ] `GET/POST /runs/{run_id}/steps/{step}`、`POST .../resolve`（§6.2.1）
- [ ] `GET /runs/{run_id}`、`GET /runs` 列表
- [ ] `GET /runs/{run_id}/events`：SSE（§6.3）
- [ ] 事件：`step_approval_required`、`step_resolved`、`run_complete`、`run_error`
- [ ] `GET /config/status`、`POST /config/save`、`GET /health`
- [ ] 兼容转发：`/select`、`/confirm`、`/rerun`（§6.2.2）
- [ ] SSE 重连：客户端 `GET /runs` + `GET /steps/{pending}`（§6.3）

### 4.2 前端

- [ ] `templates/index.html` + `static/style.css` + `static/main.js`（§6.4）
- [ ] 6 步进度条 + **步骤确认区**（满意 / 重跑 / 重选方向）
- [ ] step0：Top5 卡片 + 单选 `news_id`
- [ ] 按 step 渲染 `output`（附录 A.11）
- [ ] `approval_hints` 警告条（block_proceed、degraded、suggest_deepen_bom 等）
- [ ] 报告 Tab：Markdown 渲染（marked.js + DOMPurify）

### 4.3 P2 验收标准

- [ ] 浏览器采集 Top5 → 逐步确认至 completed
- [ ] 刷新页面后 `awaiting_step_approval` 状态可恢复确认面板
- [ ] SSE 断线重连后可继续操作

---

## 5. P3 — 财务、A 股过滤与报告落盘

**目标**：Agent5/6 达到生产可用；报告写入 `output/reports/`。

### 5.1 A 股工具

- [ ] `app/tools/finance_lookup.py`：`finance_lookup(ticker)`（§4.5.2）
- [ ] `app/tools/supplier_screen.py`：`is_eligible_a_share_main`、`filter_suppliers`
- [ ] 实现 §4.5.1 代码前缀规则 + §4.5.2 边界（ST 实时字段、退市、新股 `min_listing_days`）
- [ ] 输出 `suppliers_excluded[]` 供 step4 确认面板展示
- [ ] Agent5 流程：LLM 初筛 → `filter_suppliers` → 仅合格标的进入 `suppliers`

### 5.2 Agent6 报告

- [ ] `generate` 模式：LLM 按 §4.6 / §8.2 十章节生成
- [ ] `regenerate` 模式：Jinja2 模板 `render_report_template`（§4.6）
- [ ] 落盘：`output/reports/{run_date}_{run_id}_{slug}.md` + `runs/{run_id}/report.md`（§4.6）
- [ ] `POST /runs/{run_id}/report/regenerate`（§6.2.3）

### 5.3 P3 验收标准

- [ ] 688/300/北交所/ST 不出现在 `suppliers`
- [ ] 无合格标的时 `errors` 含 `no_eligible_a_share_main`，报告供应商节为空表说明
- [ ] 报告含 §8.2 全部章节（含检查清单、Red-team）
- [ ] `regenerate` 不调用 LLM 可产出等价结构报告

---

## 6. P4 — 扩展

- [ ] `汇总2.md` ingest 到 `cases` collection（§5.2）
- [ ] Agent3/5 检索 `cases` corpus（§5.4）
- [ ] 定时触发 Agent1（cron 或 Windows 计划任务）— 需补充 API 设计
- [ ] RAG 增量 ingest 策略（strategy 版本更新后重建索引）

---

## 7. Schema 实现清单（`app/schemas/`）

与 SPEC 附录 A 一一对应，建议文件划分：

| 模型 | 附录 | 优先级 |
|------|------|--------|
| `NewsItem` | A.1 | P1 |
| `ComponentNode` / `HorizontalBranch` | A.2 | P1 |
| `BottleneckItem` | A.3 | P1 |
| `ValidationReport` | A.4 | P1 |
| `SupplierProfile` | A.5 | P1 |
| `RedTeamReport` | A.6 | P1 |
| `ChecklistGateResult` | A.7 | P1 |
| `ApprovalHints` | A.8 | P1 |
| `RunDetail` | A.9 | P2 |
| `StepResolveRequest` | A.10 | P1 |
| `StepApprovalView` | A.11 | P2 |

- [ ] 全部模型实现并通过 JSON round-trip 校验
- [ ] LLM 调用使用 `response_format` 或 JSON mode 对齐上述模型

---

## 8. 测试与质量（按阶段插入）

不单独建测试工程目录；在各阶段完成时执行：

| 阶段 | 建议自测 |
|------|----------|
| P0 | ingest + retriever 脚本手动跑通 |
| P1 | CLI 端到端：create → resolve 全链；state.json 字段抽查 |
| P2 | 浏览器主路径 + 刷新恢复 + rerun |
| P3 | supplier_screen 单元用例：600519.SH 通过、688xxx/ST 拒绝 |
| 全阶段 | Agent 运行时 Phase1 ≤3min、Phase2 ≤13min（§9，不含人工等待） |

- [ ] 记录已知限制到 `runs/.../errors` 而非静默吞掉

---

## 9. 可选后续（SPEC P2 / v1.5，暂不阻塞 MVP）

以下 SPEC 已提及但 **不纳入 P0～P4 必做**：

- [ ] 用户确认前手改中间 JSON（`PATCH /runs/{id}/state`）
- [ ] `suppliers_excluded` 在报告正文中单独成章
- [ ] LAN 部署 + Token 鉴权
- [ ] 多用户 / 多租户
- [ ] LangGraph 迁移评估（当前明确不采用）

---

## 10. 推荐实施顺序（单线程）

```text
1. §1 工程骨架 + schemas
2. P0 RAG
3. P1 pipeline/state → gates → runner → agent1（先通 step0）
4. P1 agent2～6 逐个接通 + CLI resolve
5. P2 FastAPI + 前端确认面板
6. P3 finance_lookup + supplier_screen + Agent6 落盘
7. P4 案例库与定时任务
```

每完成一个 Agent step，建议立即用 CLI 验证 `awaiting_step_approval` + `rerun`，再接入下一步。

---

## 11. 文档同步

代码变更时同步更新：

| 变更类型 | 更新文档 |
|----------|----------|
| API / 字段变更 | SPEC.md + 本 TODOLIST 验收项 |
| 配置项新增 | `config.example.toml` + SPEC §7.1 |
| 方法论变更 | `knowledge/strategy.txt` + 重新 ingest |

---

*本清单随 SPEC v1.4.1 生成；实现过程中若 SPEC 升版，请对照 diff 调整对应章节任务。*
