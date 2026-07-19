# 知识点自动采集与每日整理

白天用热键把零星想法存进桌面暂存；晚上 10 点（或手动）调用通义千问整理成 Obsidian 笔记，成功后清空暂存。

## 你需要什么

1. **Windows**，已登录本机用户
2. **AutoHotkey v2**（采集热键）
3. **Python 3.11**（本机曾用 `D:\python3.11\python.exe`）
4. 用户环境变量 **`DASHSCOPE_API_KEY`**（通义 DashScope）
5. 依赖（首次或换机器时执行一次）：

```bat
D:\python3.11\python.exe -m pip install -r runtime\requirements.txt
```

## 日常怎么用

| 操作 | 做法 |
|------|------|
| 第一次 / 开机后挂上热键与定时任务 | 双击 **`一键启动.bat`** |
| 采集知识点 | 选中文字 → **`Ctrl+Alt+K`**（成功会弹窗） |
| 马上整理，不等晚上 | 双击 **`现在就整理.bat`** |
| 自动整理 | 每天 **22:00**（任务名 `DailyKnowledgeDigest`） |

整理成功后会清空桌面 `想法暂存.txt`；暂存为空则跳过；失败不清空。

## 路径说明

| 用途 | 路径 |
|------|------|
| 暂存 | `C:\Users\85325\Desktop\想法暂存.txt` |
| 输出笔记 | `D:\陈总的ob仓库\04_每日知识点整理\YYYY-MM-DD-知识点整理.md` |
| 整理规则 | `SKILL.md` |
| 运行配置 | `runtime\config.json` |
| 日志 | `runtime\logs\YYYY-MM-DD.log` |

每条笔记包含：**名词解释**、**常见应用**、**其他类似应用或概念**。

## 配置（可选）

编辑 `runtime\config.json`，常用项：

- `model`：当前为 `qwen-flash`（可改 `qwen-plus` 等）
- `model_server`：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- `timeout_minutes`：超时分钟数，默认 45

改完保存即可，下次整理生效，无需重新安装。

## 文件结构

```text
零星知识点收集助手\
  一键启动.bat          # 挂热键 + 注册 22:00 任务
  现在就整理.bat        # 立刻整理
  SKILL.md              # 整理规范（给大模型看）
  SPEC.md               # 设计说明
  README.md             # 本说明
  runtime\
    capture-idea.ahk    # Ctrl+Alt+K 采集
    bootstrap.ps1       # 一键启动实际逻辑
    run_digest.py       # 整理入口（Qwen-Agent）
    run_digest_wrapper.ps1
    config.json
    requirements.txt
    logs\
```

## 停用 / 运维

| 目的 | 做法 |
|------|------|
| 停热键 | 托盘退出 AutoHotkey；或删启动项里的快捷方式 |
| 禁定时 | `schtasks /Delete /TN DailyKnowledgeDigest /F` |
| 手动跑定时任务 | `schtasks /Run /TN DailyKnowledgeDigest` |
| 看是否在跑 | 任务管理器里有 `AutoHotkey64.exe` 且命令行含 `capture-idea.ahk` |

说明：电脑关机或未登录时，当天 22:00 **不会补跑**。

## 常见问题

**「现在就整理」一闪就失败**  
多为 PowerShell/依赖或 API Key 问题。看 `runtime\logs\` 最新日志；确认用户环境变量里有 `DASHSCOPE_API_KEY`（改完后新开一个 bat 窗口再试）。

**热键没反应**  
先装 AutoHotkey v2，再双击 `一键启动.bat`。

**打开暂存文件总提示是否保存**  
采集写入已落盘。尽量不要长时间开着记事本编辑该文件；热键成功后会尽量关掉仍开着「想法暂存」的记事本，避免旧内容覆盖新追加。

**整理很慢**  
可在 `config.json` 使用更快模型（当前 `qwen-flash`）。条数多、要联网搜索时仍会多花一些时间。
