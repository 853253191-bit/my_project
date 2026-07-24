<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiFetch } from '../utils/request'
import FavoriteButton from '../components/FavoriteButton.vue'
import RecipeFoodIcon from '../components/RecipeFoodIcon.vue'

interface FavItem {
  favorite_id: number
  recipe_id: string
  title?: string
  decision_summary?: string
  cuisine_main?: string
  estimated_time?: number
  ingredients?: string[]
}

const items = ref<FavItem[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const limit = 20

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch<{ items: FavItem[]; total: number }>(
      `/api/favorites?page=${page.value}&limit=${limit}`,
    )
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function onFavChange(recipeId: string, on: boolean) {
  if (!on) {
    items.value = items.value.filter((x) => x.recipe_id !== recipeId)
    total.value = Math.max(0, total.value - 1)
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>我的收藏</h1>
      <p>共 {{ total }} 道菜</p>
    </div>
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint error">{{ error }}</div>
    <div v-else-if="!items.length" class="hint">还没有收藏，去首页发现好吃的吧</div>
    <div v-else class="list">
      <article v-for="it in items" :key="it.favorite_id" class="card">
        <div class="visual">
          <RecipeFoodIcon :title="it.title || ''" :ingredients="it.ingredients" />
        </div>
        <div class="body">
          <h2>{{ it.title || it.recipe_id }}</h2>
          <p>{{ it.decision_summary || '' }}</p>
          <div class="meta">
            <span v-if="it.cuisine_main">{{ it.cuisine_main }}</span>
            <span v-if="it.estimated_time">{{ it.estimated_time }} 分钟</span>
          </div>
          <FavoriteButton
            :recipe-id="it.recipe_id"
            :initial-favorited="true"
            size="sm"
            @change="(on) => onFavChange(it.recipe_id, on)"
          />
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
  margin-bottom: 20px;
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
  gap: 8px;
  margin-bottom: 8px;
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
