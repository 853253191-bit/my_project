# 食刻 · 运维手册（稳住底盘）

适用于已上线环境：公网 IP `118.178.131.84`，项目根目录 `/opt/shike/`。

## 1. 脚本安装

将本仓库 `scripts/` 下运维脚本拷到服务器：

```bash
# 在服务器
mkdir -p /opt/shike
cp logs.sh status.sh backup.sh restore.sh /opt/shike/
chmod +x /opt/shike/*.sh
```

或从本机（已配置 SSH 时）：

```powershell
scp scripts/logs.sh scripts/status.sh scripts/backup.sh scripts/restore.sh scripts/README_OPS.md deploy@118.178.131.84:/opt/shike/
```

推荐请求日志埋点在后端代码 `backend/src/shike/api/main.py` 的 `/api/recommend` 中；更新代码后需：

```bash
sudo systemctl restart shike-backend
```

查看埋点：

```bash
./logs.sh backend 100 | grep recommend
```

---

## 2. 查看日志 — `logs.sh`

| 命令 | 作用 |
|------|------|
| `./logs.sh backend` | 实时跟踪后端（journalctl -f） |
| `./logs.sh backend 100` | 最近 100 行后端日志 |
| `./logs.sh nginx` | Nginx 访问日志 |
| `./logs.sh nginx-error` | Nginx 错误日志 |
| `./logs.sh all` | 后端 + Nginx 合并跟踪 |

示例：

```bash
cd /opt/shike
./logs.sh backend
./logs.sh backend 50
./logs.sh nginx-error
```

`journalctl` 需要权限时脚本会自动加 `sudo`。

---

## 3. 服务状态 — `status.sh`

```bash
cd /opt/shike
./status.sh
```

检查项：

- Nginx / `shike-backend` 是否 `active`
- `80` / `8000` 是否监听
- `http://127.0.0.1/api/health` 是否返回 200
- 最近后端 error 相关日志摘要

绿色 ✅ 为正常，红色 ❌ 为异常；有失败时退出码为 1。

---

## 4. 数据备份 — `backup.sh`

### 手动备份

```bash
cd /opt/shike
./backup.sh
```

产物示例：

```text
/opt/shike/backups/
├── 2026-07-24/
│   ├── recipes_backup.db
│   ├── recipes_dump.sql
│   └── chroma_backup.tar.gz
├── backup_2026-07-24.tar.gz
└── cron.log                  # 定时任务日志（安装 cron 后）
```

行为说明：

- 备份前检查磁盘可用空间，小于 **1GB** 则报警退出
- SQLite 优先用 `sqlite3 .backup`（无 sqlite3 则文件复制）
- Chroma 目录打成 `chroma_backup.tar.gz`
- 再打当日总包 `backup_YYYY-MM-DD.tar.gz`
- 自动删除 **7 天**前的备份（可用环境变量 `KEEP_DAYS` 调整）

可选环境变量：

```bash
export OSS_BUCKET=your-bucket-name   # 需已安装并配置 ossutil
export EMAIL_TO=you@example.com      # 需系统可用 mail 命令
export KEEP_DAYS=7
./backup.sh
```

### 安装每天 03:00 定时备份

```bash
cd /opt/shike
./backup.sh --install-cron
crontab -l | grep backup
```

定时输出写入：`/opt/shike/backups/cron.log`。

---

## 5. 数据恢复 — `restore.sh`

```bash
cd /opt/shike
./restore.sh /opt/shike/backups/backup_2026-07-24.tar.gz
```

流程：

1. 要求输入 `YES` 确认  
2. `systemctl stop shike-backend`  
3. 将当前 `/opt/shike/data` 安全复制到 `backups/data_before_restore_*`  
4. 恢复 `recipes.db` 与 Chroma  
5. `systemctl start shike-backend` 并做健康检查  

注意：会覆盖现有数据；务必确认备份日期正确。

---

## 6. 推荐接口日志埋点

每次 `POST /api/recommend` 成功或失败会写日志，字段包括：

- 请求时间（日志时间戳）
- `query`（用户检索短句）
- `filters`（筛选条件）
- `titles`（返回菜名列表）
- `elapsed_ms`（耗时毫秒）

查看：

```bash
./logs.sh backend 200 | grep -E 'recommend ok|recommend fail'
```

---

## 7. 常见问题排查

### 网页能开但搜索失败

```bash
./status.sh
./logs.sh backend 100
curl -s http://127.0.0.1/api/health
curl -s -X POST http://127.0.0.1/api/parse_intent \
  -H "Content-Type: application/json" \
  -d '{"text":"想喝热汤"}'
```

检查 `/opt/shike/backend/.env`：`OPENAI_API_KEY` 不要留「请填写」。

### Chroma / 推荐报 readonly

先停服务再离线迁移或从备份恢复，避免进程占用时删目录：

```bash
sudo systemctl stop shike-backend
# 再 migrate 或 ./restore.sh ...
sudo systemctl start shike-backend
```

### 备份失败：没有 sqlite3

```bash
sudo apt-get install -y sqlite3
```

### 磁盘空间不足

```bash
df -h /opt
du -sh /opt/shike/backups/*
# 可调小保留天数
KEEP_DAYS=3 ./backup.sh
```

### 外网打不开，本机 curl 正常

检查阿里云安全组是否放行 **80/TCP**。

---

## 8. 建议的日常节奏（上线第一周）

| 频率 | 动作 |
|------|------|
| 每天 | `./status.sh` 扫一眼 |
| 出问题 | `./logs.sh backend` / `nginx-error` |
| 每天 03:00 | cron 自动 `./backup.sh` |
| 改代码/迁库前 | 先手动 `./backup.sh` |
| 误删数据 | `./restore.sh backups/backup_日期.tar.gz` |

---

## 9. 相关路径速查

| 路径 | 说明 |
|------|------|
| `/opt/shike/backend` | 后端代码与 venv |
| `/opt/shike/backend/.env` | 密钥与数据路径 |
| `/opt/shike/frontend/dist` | 前端静态文件 |
| `/opt/shike/data/sqlite` | SQLite |
| `/opt/shike/data/chroma` | Chroma |
| `/opt/shike/backups` | 备份归档 |
| `/etc/systemd/system/shike-backend.service` | 后端服务单元 |
| `/etc/nginx/sites-available/shike` | Nginx 站点配置 |
