# 04 · 前端单元测试（说明入口）

实际用例不在本目录，而在前端工程内，以便复用 Vite / Vue / `@` 别名：

```text
frontend/tests/unit/
├── setup.ts
├── stores/
│   ├── workflow.spec.ts
│   ├── session.spec.ts
│   └── auth.spec.ts
└── components/
    ├── LoginView.spec.ts
    ├── WorkflowBar.spec.ts
    └── FeedbackView.spec.ts
```

## 技术栈
Vitest、happy-dom、@vue/test-utils、Pinia

## 目的
验证状态机流转、会话状态、登录态与关键表单交互，不依赖浏览器与后端。

## 怎么跑
```bash
cd ../../../frontend
npm run test:unit
```

CI 的 Frontend Build Job 会在构建前自动执行。
