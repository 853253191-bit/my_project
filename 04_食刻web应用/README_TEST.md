# 食刻 · 测试与质量保障说明

本文说明如何在本地或生产机（`/opt/shike/backend`）运行端到端 API 测试、查看报告，以及配置告警与定时冒烟。

## 1. 测试环境搭建

### 依赖安装

在后端虚拟环境中安装测试依赖：

```bash
cd /opt/shike/backend
source venv/bin/activate   # 若使用 venv
pip install -r requirements-test.txt
```

依赖包括：`pytest`、`pytest-html`、`requests`。

### 可选配置

```bash
cp .env.test.example .env.test
# 按需修改 TEST_BASE_URL / TEST_ENV
```

在生产 `.env` 中可追加告警相关项：

```bash
ALERT_EMAIL=your-email@example.com
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

### 目录结构

```text
backend/
├── run_tests.sh
├── alert.sh
├── install_smoke_cron.sh
├── requirements-test.txt
├── pytest.ini
├── .env.test.example
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_filters.py
    ├── test_semantic.py
    ├── test_expand.py
    ├── fixtures/
    │   ├── query_samples.json
    │   └── expected_results.json
    └── reports/          # JUnit / HTML / 失败请求日志
```

## 2. 运行测试

先确保后端可用（本机或 Nginx 反代）：

```bash
curl -s http://127.0.0.1:8000/api/health
```

给脚本执行权限（仅需一次）：

```bash
chmod +x run_tests.sh alert.sh install_smoke_cron.sh
# 若从 Windows 上传导致 CRLF：
sed -i 's/\r$//' run_tests.sh alert.sh install_smoke_cron.sh
```

### 常用命令

| 命令 | 说明 |
|------|------|
| `./run_tests.sh` | 默认：冒烟（健康 + 硬过滤 + 扩召回） |
| `./run_tests.sh --smoke` | 仅冒烟，目标 30 秒内完成 |
| `./run_tests.sh --full` | 完整集（含语义检索），目标 3 分钟内 |
| `./run_tests.sh --report` | 额外生成 HTML 报告 |
| `./run_tests.sh --failfast` | 首个失败即停止 |
| `./run_tests.sh --smoke --report --failfast` | 可组合 |

### 切换测试目标

```bash
# 测本机后端
TEST_BASE_URL=http://127.0.0.1:8000 ./run_tests.sh --smoke

# 测公网（经 Nginx）
TEST_ENV=production ./run_tests.sh --smoke
# 或
TEST_BASE_URL=http://118.178.131.84 ./run_tests.sh --full
```

### 失败时告警

```bash
ALERT_ON_FAIL=1 ./run_tests.sh --smoke
```

失败会调用 `alert.sh --smoke-failed`；连续 3 次冒烟失败会真正发通知。

## 3. 添加新测试

1. 在 `tests/` 新建 `test_xxx.py`，或追加到现有文件。
2. 使用 fixture `api_client` 发请求，例如：

```python
@pytest.mark.smoke
def test_demo(api_client):
    """测试目的：...；预期：..."""
    resp, data = api_client.recommend("随便吃点", filters={}, top_k=3)
    assert resp.status_code == 200
    assert data.get("items")
```

3. 打上 marker：`smoke` / `full` / `filter` / `semantic` / `expand`。
4. 失败时 `conftest` 会自动把最近一次请求写入 `tests/reports/fail_*.json`。

## 4. 测试数据维护

编辑 `tests/fixtures/query_samples.json`，追加典型用户话术：

```json
{
  "query": "新查询文案",
  "filters": {"spicy_level_max": 0},
  "expected": {"contains_any": ["汤"], "non_empty": true}
}
```

`expected_results.json` 用于存放人工回归快照说明，主断言仍以 `test_*.py` 为准。

## 5. 告警与定时任务

### 手动巡检

```bash
./alert.sh --check-health
./alert.sh --check-disk
./alert.sh --check-recommend-latency
./alert.sh --message "人为触发测试告警"
```

触发条件（脚本内实现）：

- 连续 3 次冒烟失败（`--smoke-failed` 计数）
- 健康检查 5xx / 无法连接
- 磁盘使用率 ≥ 85%（默认路径 `/opt/shike`）
- 推荐接口连续 5 次超过 3 秒或非 200

状态文件目录：`/opt/shike/data/qa/`。

### 安装每日 04:00 冒烟

```bash
bash /opt/shike/backend/install_smoke_cron.sh
crontab -l | grep smoke
```

日志：`/opt/shike/data/qa/smoke_cron.log`。

建议将 `alert.sh` 同步到 `/opt/shike/alert.sh`（安装脚本会自动复制）。

## 6. 常见问题排查

| 现象 | 处理 |
|------|------|
| 连接失败 / Connection refused | 检查 `systemctl status shike-backend`，确认 `TEST_BASE_URL` |
| 首页 200 失败 | 设置 `TEST_HOME_URL=http://127.0.0.1` 或公网首页地址 |
| 硬过滤偶发失败 | 看响应 `recall_level`；扩召回时用例会 skip 严格断言 |
| 语义「喝汤」失败 | 查看 `reports/fail_*.json` 中的返回标题；确认 Embedding/Chroma 正常 |
| 扩召回无 `recall_level` | 确认已部署新版 `recommend.py` |
| pytest 找不到包 | 使用 venv 的 python：`./venv/bin/python -m pytest` |
| 脚本 `\r` 报错 | `sed -i 's/\r$//' run_tests.sh alert.sh` |

## 7. 验收对照

- [ ] `./run_tests.sh --smoke` 约 30 秒内完成
- [ ] `./run_tests.sh --full` 约 3 分钟内完成
- [ ] 过敏原用例可拦截含「花生」的结果
- [ ] 「喝汤」语义用例至少命中一道汤/暖胃相关
- [ ] 严苛扩召回用例返回非空且 `recall_level` 为 2 或 3
- [ ] 失败时 `tests/reports/` 生成 `fail_*.json`
