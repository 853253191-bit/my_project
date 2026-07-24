<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiFetch } from '../utils/request'
import RecipeFoodIcon from '../components/RecipeFoodIcon.vue'

interface HistItem {
  history_id: number
  recipe_id: string
  query_text?: string
  created_at?: string
  title?: string
  decision_summary?: string
  cuisine_main?: string
  estimated_time?: number
  ingredients?: string[]
}

const items = ref<HistItem[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const limit = 20

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch<{ items: HistItem[]; total: number }>(
      `/api/history?page=${page.value}&limit=${limit}`,
    )
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function clearAll() {
  if (!confirm('确定清空全部浏览历史？')) return
  await apiFetch('/api/history', { method: 'DELETE' })
  items.value = []
  total.value = 0
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>浏览历史</h1>
        <p>共 {{ total }} 条记录</p>
      </div>
      <button v-if="total" type="button" class="clear-btn" @click="clearAll">清空历史</button>
    </div>
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint error">{{ error }}</div>
    <div v-else-if="!items.length" class="hint">暂无浏览记录</div>
    <div v-else class="list">
      <article v-for="it in items" :key="it.history_id" class="card">
        <div class="visual">
          <RecipeFoodIcon :title="it.title || ''" :ingredients="it.ingredients" />
        </div>
        <div class="body">
          <h2>{{ it.title || it.recipe_id }}</h2>
          <p>{{ it.decision_summary || '' }}</p>
          <div class="meta">
            <span v-if="it.query_text">查询：{{ it.query_text }}</span>
            <span v-if="it.created_at">{{ it.created_at }}</span>
          </div>
        </div>
      </article>
    </div>
    <div v-if="total > limit" class="pager">
      <button type="button" :disabled="page <= 1" @click="page--; load()">上一页</button>
      <span>第 {{ page }} 页</span>
      <button
        type="button"
        :disabled="page * limit >= total"
        @click="page++; load()"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 12px;
}
.page-head h1 {
  font-family: var(--font-title);
  font-size: 28px;
  color: var(--title);
}
.page-head p {
  color: var(--secondary);
  font-size: 14px;
}
.clear-btn {
  border: 1px solid var(--divider);
  background: #fff;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--body);
}
.hint {
  padding: 40px;
  text-align: center;
  color: var(--secondary);
}
.hint.error {
  color: #c62828;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 70vh;
  overflow: auto;
}
.card {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}
.visual {
  width: 72px;
  height: 72px;
  flex-shrink: 0;
  border-radius: 14px;
  background: linear-gradient(145deg, #fff8f0, #f5ede4);
  display: flex;
  align-items: center;
  justify-content: center;
}
.body h2 {
  font-size: 18px;
  color: var(--title);
  margin-bottom: 4px;
}
.body p {
  font-size: 13px;
  color: var(--body);
  margin-bottom: 8px;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--secondary);
}
.pager {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 20px;
  align-items: center;
}
.pager button {
  border: 1px solid var(--divider);
  background: #fff;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.pager button:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
