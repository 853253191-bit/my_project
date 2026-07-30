# 02 · 后端单元 / 集成测试（离线）

## 测什么
不启动 HTTP 服务：验证推荐辅助函数、标题去重、格式化、JWT/密码，以及临时 SQLite 仓储。

## 技术栈
Pytest、临时 SQLite（`tmp_path`）

## 目录
- `unit/` — 纯函数 / 规则逻辑
- `integration/` — 本地库表读写

## 怎么跑
```bash
export PYTHONPATH=../../../backend/src
python -m pytest -q
# 或
./run_tests.sh
```

CI 在 push 时自动执行本目录测试。
