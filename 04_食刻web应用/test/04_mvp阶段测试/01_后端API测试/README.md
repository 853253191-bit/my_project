# 01 · 后端 API 测试（黑盒冒烟）

## 测什么
对已启动的后端（本机 `8000` 或公网）发真实 HTTP 请求，验证接口可用性与推荐/过滤行为。

## 技术栈
Pytest、requests、pytest-html（可选报告）

## 主要文件
- `e2e_api/test_health.py` — 健康检查、首页、今日推荐
- `e2e_api/test_filters.py` — 辣度 / 时间 / 过敏原硬过滤
- `e2e_api/test_expand.py` — 扩召回
- `e2e_api/test_semantic.py` — 语义检索（`--full`）
- `run_tests.sh` — 统一入口；`alert.sh` — 失败告警

## 怎么跑
```bash
./run_tests.sh --smoke
TEST_BASE_URL=http://118.178.131.84 ./run_tests.sh --smoke
```
