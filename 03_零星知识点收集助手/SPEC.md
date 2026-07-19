# SPEC：知识点后台采集与每日整理

> 状态：已按本仓库 `runtime\` 实现  
> 目标：开机后采集热键自动可用；每天 22:00 自动整理，无需打开 Cursor 对话手动触发。  
> 关联 Skill：本目录 `SKILL.md`（可由 `runtime\run_digest.py` 无人值守调用）

---

## 1. 背景与目标

### 1.1 要解决什么

| 现状 | 目标 |
|------|------|
| 整理规则已写成 Skill，但必须在对话里手动喊 Agent | 22:00 由本机脚本自动调用 Qwen-Agent 执行同一套规则 |
| `Ctrl+Alt+K` 尚未实现 | 全局热键常驻后台，选中文字即可写入暂存 |
| 电脑关机则不执行 | 保持该行为：未开机 = 当天不跑，不做补跑 |

### 1.2 成功标准（验收）

1. 登录 Windows 后，无需手动操作即可使用 `Ctrl+Alt+K` 追加知识点到桌面暂存。
2. 每天 22:00（本机时区），若电脑处于开机且已登录状态，自动执行整理。
3. 整理结果写入 `D:\陈总的ob仓库\04_每日知识点整理\YYYY-MM-DD-知识点整理.md`。
4. 成功写出后清空 `C:\Users\85325\Desktop\想法暂存.txt`；无内容则不写 MD、不清空失败现场。
5. 全程不需要用户打开 Cursor 聊天窗口发指令。

### 1.3 明确不做

- 不做云端 Agent（读不到本机桌面与 `D:\`）。
- 不做关机补跑、跨天补跑。
- 清空前不留 `.bak`。
- 不劫持 `Ctrl+B`。

---

## 2. 总体架构

三块独立进程/任务，通过文件衔接：

```text
[一键] bootstrap.ps1
  ├─ 启动 AHK + 登录自启
  └─ 注册任务计划 22:00

[常驻] AutoHotkey
   Ctrl+Alt+K → 追加 → 桌面\想法暂存.txt
                              │
                              ▼
[定时] DailyKnowledgeDigest → run_digest_wrapper.ps1 → run_digest.py
                              │
                              ▼
         Qwen-Agent（加载 SKILL.md 规则 + 本地工具）
                              │
                              ▼
         Obsidian\04_每日知识点整理\日期-知识点整理.md
         + 清空 想法暂存.txt
```

| 组件 | 职责 | 生命周期 |
|------|------|----------|
| A. 采集脚本（AHK） | 全局热键写入暂存 | 开机/登录自启，一直挂着 |
| B. 定时触发（任务计划） | 22:00 启动整理入口 | 系统级，与 Cursor 窗口无关 |
| C. 整理入口脚本 | 空文件快检 → 调用 Qwen-Agent → 校验 MD | 每次定时跑完即退出 |
| D. Skill | Agent 的详细整理说明书 | 被 C 注入为 system_message |

**关键结论：** Skill 不能后台自跑；后台跑的是「入口脚本 + Qwen-Agent」。Skill 继续作为整理规范的唯一来源，避免两套逻辑分叉。

---

## 3. 路径与约定（冻结）

| 项 | 值 |
|----|-----|
| 暂存文件 | `C:\Users\85325\Desktop\想法暂存.txt` |
| Obsidian 输出目录 | `D:\陈总的ob仓库\04_每日知识点整理` |
| 输出文件名 | `YYYY-MM-DD-知识点整理.md` |
| 热键 | `Ctrl+Alt+K` |
| 定时 | 每天 `22:00`，本机本地时区 |
| Skill 路径 | `C:\Users\85325\Desktop\零星知识点收集助手\SKILL.md` |
| 工作目录 | `C:\Users\85325\Desktop\零星知识点收集助手\runtime\` |
| 日志目录 | `runtime\logs\` |
| 编码 | 全部 UTF-8 |
| API Key | 环境变量 `DASHSCOPE_API_KEY` |
| API Base | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 默认模型 | `qwen-plus`（见 `runtime\config.json`） |

### 3.1 暂存条目格式

```text
---
YYYY-MM-DD HH:mm
<选中的原文，可多行>
---
```

---

## 4. 组件 A：全局采集（AutoHotkey）

### 4.1 功能需求

1. 热键 `Ctrl+Alt+K` 全局生效（任意前台窗口）。
2. 读取当前剪贴板前，先把「当前选中」送入剪贴板：发送 `Ctrl+C`，等待短延迟后读取。
3. 若剪贴板为空或仅空白：不写文件，静默返回。
4. 若有内容：按 3.1 格式追加到暂存文件；文件不存在则创建。
5. 时间戳用本机本地时间。
6. 写文件使用 UTF-8。
7. 写入期间若文件被占用：短暂重试 2～3 次；仍失败则写日志，不弹模态框打断用户。

### 4.2 实现文件

| 文件 | 说明 |
|------|------|
| `runtime\capture-idea.ahk` | 热键与追加写入 |
| 登录自启 | `bootstrap.ps1` 写入「启动」文件夹快捷方式 |

### 4.3 验收用例

- 选中「残差连接」→ 热键 → 暂存末尾新增一块，含时间戳与原文。
- 未选中任何文字 → 热键 → 暂存内容不变。
- 连续按两次相同选中 → 暂存可出现两条相同正文（去重交给整理阶段）。

---

## 5. 组件 B：定时触发（Windows 任务计划）

### 5.1 功能需求

1. 任务名：`DailyKnowledgeDigest`。
2. 触发器：每天 22:00。
3. 条件：仅在用户已登录时运行；未开机/休眠未唤醒则当天跳过。
4. 操作：启动 `runtime\run_digest_wrapper.ps1`（内部设置 API Key 并调用 `run_digest.py`）。
5. 权限：当前用户账户（需能读写桌面与 `D:\陈总的ob仓库`）。
6. 若上一次仍在运行：不启动新实例。

### 5.2 环境变量

- 用户级设置 `DASHSCOPE_API_KEY`。
- `run_digest_wrapper.ps1` 显式从 User/Machine 环境读取并注入进程，避免任务计划非交互会话读不到 Key。

### 5.3 验收用例

- 手动 `schtasks /Run /TN DailyKnowledgeDigest` → 与直接跑 wrapper 行为一致。
- 暂存为空时任务仍成功退出（exit 0），不报错弹窗。

---

## 6. 组件 C：整理入口脚本（后台核心）

入口脚本负责「无人值守调用」，整理智能交给 **Qwen-Agent**，并明确要求其遵循 `SKILL.md`。

### 6.1 为何用 Qwen-Agent

- Skill 已规定去重、检索、写作风格；用 Agent 可复用，避免再写一套解释逻辑。
- 本机 Python 进程可直接读写桌面与 `D:\`。
- 经 DashScope OpenAI 兼容端点调用，Key 使用 `DASHSCOPE_API_KEY`。

### 6.2 功能需求

1. **快检**：若暂存不存在或去空白后为空 → 写 info 日志「跳过：无内容」→ exit 0。
2. **调用 Agent**：一次性 `Assistant.run`，将 `SKILL.md` 注入 system_message。
3. **工具**：`read_inbox` / `web_search` / `write_digest_md` / `clear_inbox`（清空仅在写出成功后由 Agent 调用）。
4. **运行时参数**（`runtime\config.json`）：
   - `model`：默认 `qwen-plus`
   - `model_server`：`https://dashscope.aliyuncs.com/compatible-mode/v1`
   - `api_key_env`：`DASHSCOPE_API_KEY`
5. **结果处理**：
   - 启动失败（认证/网络等）→ 记 error 日志，exit 1；**不清空暂存**。
   - 运行结束但未检出有效当日 MD → 记 error，exit 2；**不清空暂存**。
   - 成功 → 记 info，exit 0。
6. **日志**：`runtime\logs\YYYY-MM-DD.log`（UTF-8）。
7. **超时**：默认 45 分钟（可配置）；超时则记日志，不清空暂存。

### 6.3 技术选型（已拍板）

| 项 | 选择 |
|----|------|
| 语言 | Python 3 |
| Agent | `qwen-agent` |
| API | DashScope 兼容模式 + `DASHSCOPE_API_KEY` |

### 6.4 入口脚本伪流程

```text
main:
  log start
  if inbox missing or blank:
    log skip
    exit 0
  try:
    result = QwenAgent.run(SKILL + tools)
  catch startup_error:
    log error
    exit 1
  if 当日 MD 未有效写出:
    log error
    exit 2
  log success
  exit 0
```

---

## 7. 组件 D：Skill

现有 `SKILL.md` 覆盖整理规则；可由 `run_digest` 无人值守调用。

**原则：** 整理业务逻辑只维护在 Skill 一处；入口脚本不复制去重/写作规则。

---

## 8. 端到端交付

### 阶段 0：准备

1. 确认 Obsidian 目录 `D:\陈总的ob仓库\04_每日知识点整理` 存在（或允许脚本创建）。
2. 确认桌面可写。
3. 用户环境变量设置 `DASHSCOPE_API_KEY`。
4. 安装 Python 3；在 `runtime\` 执行 `pip install -r requirements.txt`。
5. 安装 AutoHotkey v2（若未装）。

### 阶段 1～3：一键完成

在 `runtime\` 执行：

```powershell
.\bootstrap.ps1
```

将：启动 AHK、写入登录自启、注册 `DailyKnowledgeDigest` @ 22:00。

手动试跑整理：

```powershell
.\run_digest_wrapper.ps1
# 或
schtasks /Run /TN DailyKnowledgeDigest
```

---

## 9. 失败与边界

| 场景 | 期望行为 |
|------|----------|
| 22:00 电脑关机 | 不执行、不补跑 |
| 22:00 休眠且未唤醒 | 当天可视为跳过 |
| 暂存为空 | 入口快检跳过，exit 0 |
| Agent 中途失败 | 不清空暂存，留待下次或手动再跑 |
| 同日重复触发 | Skill 规定覆盖同名 MD；任务计划避免并行双开 |
| `D:\` 盘不可用 | 记错误，不清空暂存 |
| 无网络 | 搜索失败时按 Skill 标明不确定；若未写出 MD 则 exit 2 且不清空 |

---

## 10. 配置清单

| 配置项 | 位置 | 备注 |
|--------|------|------|
| `DASHSCOPE_API_KEY` | 用户环境变量 | wrapper 会显式读取 |
| 热键脚本 | `runtime\capture-idea.ahk` | 自启指向它 |
| 入口 | `runtime\run_digest.py` | 经 wrapper 调用 |
| 模型/超时等 | `runtime\config.json` | 可改而不改代码 |

---

## 11. 产出物清单

```text
C:\Users\85325\Desktop\零星知识点收集助手\
  SKILL.md
  SPEC.md
  runtime\
    capture-idea.ahk
    run_digest.py
    run_digest_wrapper.ps1
    bootstrap.ps1
    requirements.txt
    config.json
    logs\
```

另加：Windows 任务计划中的 `DailyKnowledgeDigest`；登录自启中的 AHK 快捷方式。

---

## 12. 常用运维

| 操作 | 命令/做法 |
|------|-----------|
| 停热键 | 托盘退出 AutoHotkey；或删启动项快捷方式 |
| 禁定时 | `schtasks /Delete /TN DailyKnowledgeDigest /F` |
| 看日志 | `runtime\logs\YYYY-MM-DD.log` |
| 改模型 | 编辑 `runtime\config.json` 的 `model` 字段 |
