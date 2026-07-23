<template>
  <div>
    <div class="card recipe-result">
      <h2>为你推荐的食谱</h2>
      <div v-if="!content" class="loading-text">加载中...</div>
      <div v-else class="recipe-content" v-html="renderedContent" />
      <RecipeCard :sources="sources" />
    </div>

    <ChatPanel v-if="sessionId" :session-id="sessionId" @updated="onUpdated" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchSession } from '../api/client'
import { useSessionStore } from '../stores/session'
import ChatPanel from '../components/ChatPanel.vue'
import RecipeCard from '../components/RecipeCard.vue'

const props = defineProps<{
  sessionId: string
}>()

const store = useSessionStore()
const content = ref(store.recipeContent)
const sources = ref(store.sources)

function simpleMarkdown(text: string): string {
  return text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\n/g, '<br>')
}

const renderedContent = computed(() => simpleMarkdown(content.value))

async function loadSession() {
  if (store.recipeContent) {
    content.value = store.recipeContent
    sources.value = store.sources
    return
  }
  try {
    const data = await fetchSession(props.sessionId)
    content.value = data.last_recipe?.content || ''
    sources.value = data.sources || []
  } catch {
    content.value = '会话已过期，请返回首页重新生成'
  }
}

function onUpdated() {
  content.value = store.recipeContent
  sources.value = store.sources
}

onMounted(loadSession)
</script>

<style scoped>
.recipe-result h2 {
  margin-bottom: 16px;
  color: var(--color-primary);
}
.loading-text {
  color: var(--color-text-light);
  padding: 20px 0;
}
</style>
