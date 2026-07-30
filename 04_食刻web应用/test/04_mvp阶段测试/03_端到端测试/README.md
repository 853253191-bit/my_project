# 03 · 端到端测试（Playwright）

## 测什么
浏览器里走真实用户可见路径：推荐主流程、登录入口守卫、反馈页。

## 技术栈
Playwright（Chromium）、Vite preview（同源 `/api` 反代）

## 用例
- `specs/core-flow.spec.ts` — 对话推荐 → 详情 → 关闭 → 重置
- `specs/auth-gate.spec.ts` — 收藏跳转登录、登录/注册互跳、空提交
- `specs/feedback.spec.ts` — 反馈校验与提交

## 怎么跑
```bash
# 前端需先有 dist
cd ../../../frontend && npm run build
cd ../test/04_mvp阶段测试/03_端到端测试
npm ci && npx playwright install chromium
npm run test:e2e
```
