<template>
  <div class="card about-page">
    <h2>关于食刻</h2>
    <p>
      食刻（Shike）是一款基于大语言模型与检索增强生成（RAG）技术的智能饮食决策 Web 应用。
    </p>
    <h3>核心功能</h3>
    <ul>
      <li>根据心情、口味、天气、人数等情境生成个性化食谱</li>
      <li>基于本地食谱知识库的 RAG 检索，推荐有据可依</li>
      <li>生成后可继续对话微调，灵活调整推荐结果</li>
      <li>展示参考来源，降低 AI 幻觉风险</li>
    </ul>
    <h3>技术栈</h3>
    <ul>
      <li>前端：Vue 3 + Vite + TypeScript</li>
      <li>后端：FastAPI + Chroma + SQLite</li>
      <li>大模型：阿里云 DashScope 通义千问</li>
      <li>部署：Docker Compose + Vercel</li>
    </ul>
  </div>
</template>

<style scoped>
.about-page h2 {
  margin-bottom: 12px;
  color: var(--color-primary);
}
.about-page h3 {
  margin: 20px 0 8px;
}
.about-page p,
.about-page li {
  line-height: 1.8;
  color: var(--color-text);
}
.about-page ul {
  padding-left: 20px;
}
</style>
