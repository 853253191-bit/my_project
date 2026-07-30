# 食刻 · 测试说明

本文说明 `04_食刻web应用/test` 目录的组织方式、本次已落地的测试内容、技术栈与测试目的。

---

## 1. 目录怎么分

测试统一落在 `test/04_mvp阶段测试/`（便于 CI 固定路径引用）。按「测什么」分成四类：

```text
test/
├── README.md                          # 本说明
├── .gitignore                         # 忽略缓存、报告、node_modules
└── 04_mvp阶段测试/
    ├── 01_后端API测试/                # 黑盒：对真实/公网 API 发 HTTP
    ├── 02_后端单元集成/               # 白盒：函数级 + 临时 SQLite
    ├── 03_端到端测试/                 # Playwright：浏览器里走用户路径
    └── 04_前端单元测试/               # 说明入口（实际用例在 frontend/tests）
```

| 目录 | 类型 | 是否依赖线上服务 | CI |
|------|------|------------------|-----|
| `01_后端API测试` | API 冒烟 / 回归 | 是（本机或公网 API） | 手动触发 |
| `02_后端单元集成` | 单元 + 轻量集成 | 否 | push 自动 |
| `03_端到端测试` | E2E | 半依赖（preview 反代线上 `/api`） | 手动触发 |
| `04_前端单元测试` | 指向 Vitest | 否 | push 自动（在 frontend Job） |

前端单元测试代码实际位置：

- `frontend/tests/unit/stores/`（Pinia）
- `frontend/tests/unit/components/`（Vue 组件）

放在 `frontend/` 下是为了与 Vite / `@` 别名 / Vue 插件同一工程，避免路径断裂。

---

## 2. 本次做了哪些测试

### 2.1 后端 API 黑盒（`01_后端API测试`）

**目的：** 在「服务已启动」的前提下，验证对外 HTTP 接口行为是否符合预期，尽早发现部署后链路断裂、过滤失效、召回异常。

**覆盖：**

- 健康检查：`/api/health`、首页可达、今日推荐条数
- 硬过滤：辣度上限、烹饪时间、过敏原排除
- 扩召回：严苛条件下是否出现 `recall_level`、结果非空
- 语义检索（full）：如「喝汤」、蛋番茄、庆祝类意图

**怎么跑：**

```bash
cd test/04_mvp阶段测试/01_后端API测试
./run_tests.sh --smoke          # 冒烟
TEST_ENV=production ./run_tests.sh --smoke
```

---

### 2.2 后端单元 / 集成（`02_后端单元集成`）

**目的：** 不启动完整服务、不打公网，快速验证核心业务函数与本地 SQLite 行为，把逻辑错误挡在合入前。

**单元（`unit/`）：**

- 推荐辅助：理由生成、过滤放宽、偏好合并、收藏加权排序
- 标题去重：规范化、相似度、模糊去重
- 菜谱格式化：食材名提取、Markdown 详情拼接
- 安全：密码哈希校验、JWT 签发与解码
- Pipeline 基础：种子菜谱、清洗、切块、检索 query 构建

**集成（`integration/`）：**

- 临时 SQLite：`upsert` / `get_by_id`、站点反馈写入与列表

**怎么跑：**

```bash
cd test/04_mvp阶段测试/02_后端单元集成
export PYTHONPATH=../../../backend/src
python -m pytest -q
# 或
./run_tests.sh
```

---

### 2.3 前端单元 / 组件（`frontend/tests/unit`，说明见 `04_前端单元测试`）

**目的：** 验证状态机与关键交互逻辑，不依赖浏览器与后端。CI 每次 push 相关改动都会跑。

**Store：**

- `workflow`：合法/非法流转、详情开闭回退、错误与重置
- `session`：意图回填、标签重建、本地「我的食谱」
- `auth`：登录态、logout、login/fetchMe（mock API）

**组件：**

- `LoginView`：空表单校验、登录成功跳转
- `WorkflowBar`：展开收起、清空流转记录
- `FeedbackView`：字数校验、提交成功提示

**怎么跑：**

```bash
cd frontend
npm run test:unit
```

---

### 2.4 端到端 Playwright（`03_端到端测试`）

**目的：** 用真实浏览器验证「用户看得见」的关键旅程，捕获前后端联调、路由守卫、页面结构回归问题。

**旅程：**

1. **核心推荐流**：对话输入 → 推荐列表 → 打开详情 → 关闭 → 重置  
2. **鉴权入口**：未登录访问收藏跳转登录、登录/注册互跳、空提交校验  
3. **反馈页**：短内容校验、合法内容提交（成功或后端错误可见其一）

**怎么跑：**

```bash
cd frontend && npm run build   # 首次或改了前端后需要
cd ../test/04_mvp阶段测试/03_端到端测试
npm ci
npx playwright install chromium
npm run test:e2e
```

也可从 `frontend`：`npm run test:e2e`。

---

### 2.5 CI 挂载情况

工作流：仓库根目录 `.github/workflows/ci-cd-bootstrap.yml`

| Job | 触发 | 作用 |
|-----|------|------|
| Frontend Build | push / PR（改动食刻相关路径） | Vitest + `npm run build` |
| Backend Unit/Integration | 同上 | 离线 pytest |
| API Smoke / Playwright / Deploy | `workflow_dispatch` 手动勾选 | 联调与发布，避免每次 push 绑死线上 |

---

## 3. 技术栈一览

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端 API 黑盒 | Pytest + requests | 对真实 HTTP 接口断言 |
| 后端单元/集成 | Pytest + 临时 SQLite | 纯函数与仓储 |
| 前端单元 | Vitest + happy-dom + @vue/test-utils + Pinia | Store / 组件 |
| 端到端 | Playwright（Chromium） | 浏览器用户旅程 |
| 持续集成 | GitHub Actions | 自动门禁 + 手动冒烟/部署 |
| 运维辅助 | `run_tests.sh` / `alert.sh` / cron 安装脚本 | 本地与服务器定时冒烟 |

未在本次落地（可选后续）：MSW、Pact 契约测试、完整「注册→登录→收藏→登出」E2E。

---

## 4. 测试目的（为什么要测这些）

1. **守住推荐主链路**  
   对话 → 意图 → 检索 → 列表 → 详情是产品核心。API 冒烟 + E2E 核心流共同保证「能推荐、能看懂、能关得上」。

2. **守住过滤与安全边界**  
   辣度/时间/过敏原属于硬约束；密码与 JWT 属于账户安全。单元测试保证规则本身正确，API 测试保证规则在线上仍生效。

3. **守住前端状态与交互**  
   首页用轻量状态机驱动 UI。Store/组件单测保证流转合法、表单校验可靠，减少「页面卡死/按钮无效」类回归。

4. **把慢测试与快测试分开**  
   单元测试秒级、可进 CI 门禁；打公网 / 开浏览器的慢测试手动或定时跑，避免每次 push 被网络与 LLM 耗时拖垮。

5. **方便排查**  
   API 失败写 `reports/fail_*.json`；E2E 失败保留截图/trace；状态机栏可见 phase，便于定位卡在哪一步。

---

## 5. 建议的日常用法

- **改业务逻辑 / 前端**：本地 `npm run test:unit` + 后端 `pytest`，再 push 等 CI  
- **发版前**：手动跑 API `--smoke` + Playwright  
- **生产巡检**：服务器 cron + `01_后端API测试/run_tests.sh --smoke`

如需扩展，优先顺序建议：完整登录旅程 E2E → CI 可选自动 API 冒烟 → MSW/Pact（协作接口稳定后再上）。
