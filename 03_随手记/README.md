# 随手记

白天用热键把选中的文字丢进暂存；登录或每晚 22:00（也可手动）由本机脚本调用通义千问，整理成 Obsidian 笔记并写入仓库。全程在 Windows 后台运行，不需要打开 Cursor 对话。

## 它能做什么

| 能力 | 说明 |
|------|------|
| 热键采集 | 选中文字后一键追加到暂存文件，带时间戳 |
| 每日知识点整理 | 去重、联网检索、按固定模板写成当天一篇总览 MD |
| 分类笔记归档 | 暂存目录下的 `.txt` 改写成 MD，归档到 Obsidian 同名目录 |
| 日记归档 | 日记暂存只归档当天内容，归档后清除当天块、保留文件 |
| 目录同步 | 暂存里新增的文件夹自动在 Obsidian 仓库创建对应目录 |
| 定时执行 | 每天 22:00 自动跑；关机或未登录则不补跑 |

知识点整理后，每条笔记包含：**名词解释**、**常见应用**、**其他类似应用或概念**。

## 工作流程

```text
  白天                         晚上 / 手动
    |                              |
    v                              v
 Ctrl+Alt+K/J              run_nightly.py
    |                              |
    v                    +---------+---------+
 暂存文件/*.txt          |                   |
                         v                   v
                  run_digest.py        run_archive.py
                  (每日知识点)          (其余 txt 归档)
                         |                   |
                         v                   v
              Obsidian 仓库/*.md      Obsidian 仓库/*.md
```

整理入口为 `runtime\run_nightly.py`：先跑每日知识点，再归档其余暂存 txt。知识点整理失败时仍会尝试归档，失败项不会被删除。

## 环境要求

1. **Windows 10/11**，已登录本机用户
2. **AutoHotkey v2** — 全局热键采集（[官网下载](https://www.autohotkey.com/)）
3. **Python 3.11**
4. 用户环境变量 **`DASHSCOPE_API_KEY`** — 通义 DashScope API Key

首次安装依赖（换机器时也需执行一次）：

```bat
python -m pip install -r runtime\requirements.txt
```

## 快速开始

1. 设置环境变量 `DASHSCOPE_API_KEY`（用户级），改完后新开终端生效。
2. 编辑 `runtime\config.json`，确认 `staging_dir`、`vault_dir` 等路径指向你的实际目录（见下方「路径与配置」）。
3. 双击 **`一键启动.bat`**：
   - 启动采集热键脚本
   - 写入登录自启（下次开机自动挂热键并检查暂存）
   - 注册计划任务 `DailyKnowledgeDigest`（每天 22:00）
   - 立即检查一次暂存（同步目录 + 归档待处理 txt）

## 日常使用

| 操作 | 做法 |
|------|------|
| 第一次 / 重装后初始化 | 双击 **`一键启动.bat`** |
| 采集知识点 | 选中文字 → **`Ctrl+Alt+K`**（成功会弹窗） |
| 采集日记 | 选中文字 → **`Ctrl+Alt+J`** |
| 立刻整理，不等 22:00 | 双击 **`现在就整理.bat`** |
| 登录后自动 | 热键自启 + 后台检查暂存 |
| 自动整理 | 每天 **22:00**（任务名 `DailyKnowledgeDigest`） |

### 暂存条目格式

热键写入的每条内容形如：

```text
---
2026-07-21 16:30
选中的原文，可多行
---
```

### 两类暂存的使用方式

**热键暂存（自动追加）**

- `04_每日知识点整理\想法暂存.txt` — `Ctrl+Alt+K`
- `11_小陈日记\日记暂存.txt` — `Ctrl+Alt+J`

**分类笔记（手动放入 txt）**

在 `暂存文件\` 下按 Obsidian 目录结构新建文件夹，把内容保存为 `.txt` 即可。例如：

```text
暂存文件\
  02_ai相关\04_模型微调\01_大模型微调原理.txt
  08_食刻应用\01_项目描述.txt
```

整理时会：同步新目录到仓库 → 将非空 txt 改写成 md → 成功后**删除 txt**（日记目录除外）。

## 路径与配置

核心路径在 `runtime\config.json` 中维护。若项目从桌面挪到其它位置，**务必更新此文件**，否则 Python 脚本仍会读写旧路径。

| 配置项 | 含义 | 示例 |
|--------|------|------|
| `staging_dir` | 暂存根目录 | `D:\myproject\03_随手记\暂存文件` |
| `vault_dir` | Obsidian 仓库根目录 | `D:\陈总的ob仓库` |
| `digest_folder` / `digest_inbox` | 知识点暂存相对路径 | `04_每日知识点整理` / `想法暂存.txt` |
| `diary_folder` / `diary_inbox` | 日记暂存相对路径 | `11_小陈日记` / `日记暂存.txt` |
| `skill_path` | 每日整理规则 | `skills\SKILL.md` |
| `archive_skill_path` | txt 归档改写规则 | `skills\SKILL-archive.md` |

输出位置（相对 `vault_dir`）：

| 类型 | 输出文件 |
|------|----------|
| 每日知识点 | `04_每日知识点整理\YYYY-MM-DD-知识点整理.md` |
| 日记 | `11_小陈日记\YYYY-MM-DD-日记.md` |
| 分类笔记 | 与暂存路径同名，扩展名改为 `.md` |

### 可选参数

| 配置项 | 默认 | 说明 |
|--------|------|------|
| `model` | `qwen-flash` | 可改为 `qwen-plus` 等 |
| `model_server` | DashScope 兼容端点 | 一般不用改 |
| `timeout_minutes` | `45` | Agent 超时分钟数 |

改完保存即可，下次整理生效。

> **说明：** 热键脚本 `capture-idea.ahk` 使用相对路径读写暂存，与 `config.json` 无关。若两处路径不一致，会出现「热键写 A、整理读 B」的情况，请保持统一。

## 目录结构

```text
03_随手记\
  一键启动.bat              # 挂热键 + 注册 22:00 任务 + 首次归档检查
  现在就整理.bat            # 立刻执行 run_nightly
  skills\
    SKILL.md                  # 每日知识点整理规范（Agent 遵循）
    SKILL-archive.md          # 普通 txt 归档改写规范
  SPEC.md                   # 设计说明（开发参考）
  README.md                 # 本说明
  暂存文件\                 # 采集与手动放置的 txt
    04_每日知识点整理\
      想法暂存.txt
    11_小陈日记\
      日记暂存.txt
    <其它分类>\*.txt
  runtime\
    capture-idea.ahk        # Ctrl+Alt+K / Ctrl+Alt+J
    bootstrap.ps1           # 一键启动逻辑
    startup.ps1             # 登录自启：热键 + 后台归档检查
    run_nightly.py          # 每晚总入口
    run_digest.py           # 每日知识点整理（Qwen-Agent）
    run_archive.py          # 目录同步 + txt 归档
    run_digest_wrapper.ps1  # 加载 API Key 并调用 Python
    config.json
    requirements.txt
    logs\                   # YYYY-MM-DD.log
```

## 整理规则摘要

**每日知识点**（`SKILL.md`）

- 读取 `想法暂存.txt` → 解析去重 → 联网检索 → 写出当天 MD → 成功后清空暂存
- 暂存为空则跳过，不创建空文件
- 写出失败则**不清空**暂存

**分类 txt 归档**（`SKILL-archive.md`）

- 保留原意，结构化改写为学习笔记风格的 Markdown
- 归档成功后删除原 txt，保留文件夹

**日记**

- `日记暂存.txt`：只取当天块归档，清除当天内容后**保留 txt 文件**
- `11_小陈日记\` 下其它 txt：标题 + 原文直接归档，**保留 txt**

## 运维

| 目的 | 做法 |
|------|------|
| 停热键 | 托盘退出 AutoHotkey；或删除启动文件夹中的 `KnowledgeCapture-CtrlAltK.lnk` |
| 禁用定时 | `schtasks /Delete /TN DailyKnowledgeDigest /F` |
| 手动触发定时任务 | `schtasks /Run /TN DailyKnowledgeDigest` |
| 查看是否在跑 | 任务管理器中有 `AutoHotkey64.exe` 且命令行含 `capture-idea.ahk` |
| 查看日志 | `runtime\logs\` 下当天日志 |

电脑关机或未登录时，当天 22:00 **不会补跑**。

## 常见问题

**「现在就整理」一闪就失败**

多为 API Key 或 Python 依赖问题。查看 `runtime\logs\` 最新日志；确认用户环境变量中有 `DASHSCOPE_API_KEY`（设置后新开 bat 窗口再试）。

**热键没反应**

确认已安装 AutoHotkey v2，再双击 `一键启动.bat`。任务管理器中应能看到 `capture-idea.ahk` 进程。

**热键有反应，但整理读不到内容**

检查 `config.json` 的 `staging_dir` / `inbox_path` 是否与项目实际位置一致（见「路径与配置」）。

**打开暂存文件总提示是否保存**

采集写入已落盘。尽量不要长时间用记事本开着暂存文件编辑；热键成功后会尝试关闭仍打开的「想法暂存」「日记暂存」记事本窗口，避免旧内容覆盖新追加。

**整理很慢**

可在 `config.json` 使用更快模型（当前 `qwen-flash`）。知识点条数多、需要联网搜索时仍会多花一些时间。

**部分 txt 归档失败**

失败项不会被删除，修复问题后再次运行 `现在就整理.bat` 或等待 22:00 自动重试。查看日志中 `run_archive` 段的错误详情。
