<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiFetch } from '../utils/request'
import { generateRecipe, getRecipeDetail } from '../api/client'
import { simpleMarkdown } from '../utils/markdown'
import { useSessionStore } from '../stores/session'
import FavoriteButton from '../components/FavoriteButton.vue'
import RecipeFoodIcon from '../components/RecipeFoodIcon.vue'
import ChatPanel from '../components/ChatPanel.vue'

interface FavItem {
  favorite_id: number
  recipe_id: string
  title?: string
  decision_summary?: string
  cuisine_main?: string
  estimated_time?: number
  ingredients?: string[]
}

const store = useSessionStore()
const items = ref<FavItem[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const limit = 20

const showDetail = ref(false)
const detailLoading = ref(false)
const detailItem = ref<FavItem | null>(null)

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
    // 详情里取消收藏时同步关闭标记
    if (detailItem.value?.recipe_id === recipeId) {
      // 仍可继续看详情，只是列表已移除
    }
  }
}

async function recordHistory(recipeId: string, title?: string) {
  try {
    await apiFetch('/api/history', {
      method: 'POST',
      json: {
        recipe_id: recipeId,
        query_text: title || undefined,
      },
    })
  } catch {
    /* ignore */
  }
}

async function openDetail(it: FavItem) {
  detailItem.value = it
  showDetail.value = true
  detailLoading.value = true
  store.recipeContent = ''
  store.sources = []
  await recordHistory(it.recipe_id, it.title)

  try {
    if (it.recipe_id) {
      const detail = await getRecipeDetail(it.recipe_id)
      store.recipeContent = detail.content || ''
      if (detail.session_id) store.setSession(detail.session_id)
      store.setSources([{
        id: detail.id,
        title: detail.title,
        source_url: detail.source_url || '',
      }])
      return
    }

    const formData = {
      mood: '',
      taste: [] as string[],
      spice_level: 0,
      servings: 2,
      cook_time: '',
      health_goal: '',
      ingredients: it.ingredients || [],
      city: '苏州',
      free_text: it.title || it.recipe_id,
    }

    for await (const evt of generateRecipe(formData)) {
      if (evt.event === 'session') {
        store.setSession(evt.data.session_id as string)
      }
      if (evt.event === 'sources') {
        store.setSources(evt.data.recipes as never[])
      }
      if (evt.event === 'recipe_chunk') {
        if (detailLoading.value) detailLoading.value = false
        store.appendContent(evt.data.content as string)
      }
    }
  } catch (err) {
    store.recipeContent = '生成失败，请重试'
    console.error(err)
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  showDetail.value = false
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>我的收藏</h1>
      <p>共 {{ total }} 道菜 · 点击卡片可查看详情</p>
    </div>
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint error">{{ error }}</div>
    <div v-else-if="!items.length" class="hint">📭 收藏夹空空如也～去首页挑几道喜欢的吧！</div>
    <div v-else class="list">
      <article
        v-for="it in items"
        :key="it.favorite_id"
        class="card"
        role="button"
        tabindex="0"
        @click="openDetail(it)"
        @keydown.enter="openDetail(it)"
      >
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
          <div class="card-actions" @click.stop>
            <FavoriteButton
              :recipe-id="it.recipe_id"
              :initial-favorited="true"
              size="sm"
              @change="(on) => onFavChange(it.recipe_id, on)"
            />
            <button type="button" class="btn-detail" @click="openDetail(it)">查看详情</button>
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

  <Teleport to="body">
    <div v-if="showDetail" class="detail-overlay" @click.self="closeDetail">
      <div class="detail-modal">
        <div class="detail-header">
          <h2>食谱详情{{ detailItem?.title ? ` · ${detailItem.title}` : '' }}</h2>
          <div class="detail-header-actions" @click.stop>
            <FavoriteButton
              v-if="detailItem?.recipe_id"
              :recipe-id="detailItem.recipe_id"
              :initial-favorited="true"
              size="md"
              @change="(on) => onFavChange(detailItem!.recipe_id, on)"
            />
            <button class="detail-close" type="button" @click="closeDetail">关闭</button>
          </div>
        </div>
        <div class="detail-body">
          <div v-if="detailLoading && !store.recipeContent" class="detail-loading">正在加载食谱…</div>
          <div v-if="store.recipeContent" class="recipe-content" v-html="simpleMarkdown(store.recipeContent)" />
          <ChatPanel v-if="store.sessionId && !detailLoading" :session-id="store.sessionId" />
        </div>
      </div>
    </div>
  </Teleport>
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
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
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
.card-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.btn-detail {
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  font-family: var(--font-body);
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

.detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(40, 28, 18, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}
.detail-modal {
  background: var(--card);
  border-radius: var(--radius-lg);
  max-width: 720px;
  width: 100%;
  max-height: 85vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--divider);
}
.detail-header h2 {
  font-family: var(--font-title);
  font-size: 20px;
  color: var(--title);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.detail-close {
  border: 1px solid var(--divider);
  background: #fff;
  font-size: 14px;
  color: var(--body);
  cursor: pointer;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-family: var(--font-body);
}
.detail-body {
  padding: 24px;
  overflow-y: auto;
}
.detail-loading {
  text-align: center;
  padding: 40px;
  color: var(--secondary);
}
.recipe-content {
  font-size: 15px;
  line-height: 1.7;
  color: var(--body);
}
.recipe-content :deep(h1),
.recipe-content :deep(h2),
.recipe-content :deep(h3) {
  color: var(--title);
  margin: 16px 0 8px;
}
.recipe-content :deep(ul) {
  padding-left: 20px;
  margin: 8px 0;
}
</style>
