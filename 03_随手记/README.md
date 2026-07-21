# 知识点自动采集与每日整理

白天用热键把零星想法存进项目暂存文件；登录启动或晚上 10 点（或手动）调用通义千问整理成 Obsidian 笔记，成功后清空/删除暂存文档。

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
| 第一次 / 开机后挂上热键与定时任务 | 双击 **`一键启动.bat`**（同时会检查暂存并归档） |
| 采集知识点 | 选中文字 → **`Ctrl+Alt+K`**（成功会弹窗） |
| 采集日记 | 选中文字 → **`Ctrl+Alt+J`** |
| 马上整理，不等晚上 | 双击 **`现在就整理.bat`** |
| 登录自动检查 | 开机登录后自动：热键 + 同步新目录 + 归档待处理 txt |
| 自动整理 | 每天 **22:00**（任务名 `DailyKnowledgeDigest`） |

整理成功后会清空 `暂存文件\04_每日知识点整理\想法暂存.txt`；暂存为空则跳过；失败不清空。

其它分类文件夹（如 `05_后端知识`、`06_全栈知识`、`07_前端知识`）请自行把内容复制成 txt 放进去；**登录启动**或 **22:00** 会：
1. 同步暂存里新增的文件夹到 `D:\陈总的ob仓库`（只建目录，不删仓库内容）
2. 将非空 txt 改写成 md 归档到对应目录，成功后**删除 txt**，**保留文件夹**
3. `11_小陈日记` 仍保留 txt（日记暂存只清当天内容）

## 路径说明

| 用途 | 路径 |
|------|------|
| 知识点暂存 | `暂存文件\04_每日知识点整理\想法暂存.txt`（`Ctrl+Alt+K`） |
| 日记暂存 | `暂存文件\11_小陈日记\日记暂存.txt`（`Ctrl+Alt+J`） |
| 分类笔记暂存 | `暂存文件\<分类>\*.txt`（如 `05_后端知识`、`06_全栈知识`、`07_前端知识`，手动放入） |
| 输出仓库 | `D:\陈总的ob仓库\<同名分类>\*.md` |
| 整理规则 | `skills\SKILL.md`、`skills\SKILL-archive.md` |
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
随手记\
  一键启动.bat          # 挂热键 + 注册 22:00 任务
  现在就整理.bat        # 立刻整理
  skills\
    SKILL.md              # 每日知识点整理规范
    SKILL-archive.md      # 普通 txt 归档改写规范
  SPEC.md               # 设计说明
  README.md             # 本说明
  暂存文件\
    04_每日知识点整理\
      想法暂存.txt      # Ctrl+Alt+K，整理后清空
    05_后端知识\
      *.txt             # 手动放入，归档后删除
    06_全栈知识\
      *.txt             # 手动放入，归档后删除
    07_前端知识\
      *.txt             # 手动放入，归档后删除
    11_小陈日记\
      日记暂存.txt      # Ctrl+Alt+J，归档后仅清当天内容
  runtime\
    capture-idea.ahk    # Ctrl+Alt+K / Ctrl+Alt+J 采集
    startup.ps1         # 登录启动：热键 + 后台归档检查
    bootstrap.ps1       # 一键启动实际逻辑
    run_digest.py       # 整理入口（Qwen-Agent）
    run_archive.py      # 目录同步 + txt 归档
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
