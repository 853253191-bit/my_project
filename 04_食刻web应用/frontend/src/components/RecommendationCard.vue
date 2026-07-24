<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RecommendItem } from '../api/client'
import { spicyLabel, timeLabel, greasinessLabel, difficultyLabel, submitFeedback } from '../api/client'
import { useSessionStore } from '../stores/session'
import { useAuthStore } from '../stores/auth'
import { apiFetch } from '../utils/request'
import RecipeFoodIcon from './RecipeFoodIcon.vue'
import FavoriteButton from './FavoriteButton.vue'

const props = defineProps<{ item: RecommendItem }>()
const emit = defineEmits<{
  (e: 'change'): void
  (e: 'detail', item: RecommendItem): void
  (e: 'added'): void
}>()

const store = useSessionStore()
const auth = useAuthStore()
const alreadyAdded = computed(() => store.isInMyRecipes(props.item.id))
const reasonText = computed(
  () => props.item.reason || props.item.decision_summary || '',
)

const rated = ref<'good' | 'bad' | null>(null)
const feedbackBusy = ref(false)

async function handleFeedback(rating: 'good' | 'bad') {
  if (rated.value || feedbackBusy.value) return
  feedbackBusy.value = true
  try {
    await submitFeedback({
      recipe_id: props.item.id,
      rating,
      session_id: store.sessionId || undefined,
      user_id: auth.user?.id ? String(auth.user.id) : undefined,
      query_text: store.queryText || store.lastIntentText || undefined,
      filters: store.filters,
    })
    rated.value = rating
  } catch (err) {
    console.error(err)
  } finally {
    feedbackBusy.value = false
  }
}

async function recordHistory() {
  if (!auth.isLoggedIn || !props.item.id) return
  try {
    await apiFetch('/api/history', {
      method: 'POST',
      json: {
        recipe_id: props.item.id,
        query_text: store.queryText || store.lastIntentText || undefined,
      },
    })
  } catch {
    /* 浏览记录失败不影响主流程 */
  }
}

function handleChange() {
  emit('change')
}
async function handleDetail() {
  await recordHistory()
  emit('detail', props.item)
}
function handleAdd() {
  const ok = store.addToMyRecipes(props.item)
  if (ok) emit('added')
}

function metaTags(item: RecommendItem) {
  const tags: string[] = []
  if (item.cuisine_main) tags.push(`🏠 ${item.cuisine_main}`)
  if (item.estimated_time) tags.push(`⏱ ${timeLabel(item.estimated_time)}`)
  if (item.spicy_level !== undefined) tags.push(`🌶 ${spicyLabel(item.spicy_level)}`)
  if (item.ai_difficulty) tags.push(`📝 ${difficultyLabel(item.ai_difficulty)}`)
  if (item.greasiness) tags.push(`🫗 ${greasinessLabel(item.greasiness)}`)
  return tags
}
</script>

<template>
  <div class="result-card anim-bounce-in">
    <div class="result-card-visual">
      <RecipeFoodIcon :title="item.title" :ingredients="item.ingredients" />
    </div>
    <div class="result-card-body">
      <div class="result-card-title-row">
        <div class="result-card-name">{{ item.title }}</div>
        <FavoriteButton
          :recipe-id="item.id"
          :initial-favorited="item.is_favorited"
          size="md"
        />
      </div>
      <div class="result-card-desc">{{ reasonText }}</div>
      <div v-if="metaTags(item).length" class="result-card-meta">
        <span v-for="(tag, i) in metaTags(item)" :key="i">{{ tag }}</span>
      </div>
      <div class="result-card-actions">
        <button class="btn-change btn-pulse" type="button" @click="handleChange">换一道 🔄</button>
        <button
          class="btn-fb btn-fb-good"
          type="button"
          :disabled="!!rated || feedbackBusy"
          :class="{ active: rated === 'good' }"
          title="好评"
          @click="handleFeedback('good')"
        >
          赞
        </button>
        <button
          class="btn-fb btn-fb-bad"
          type="button"
          :disabled="!!rated || feedbackBusy"
          :class="{ active: rated === 'bad' }"
          title="差评"
          @click="handleFeedback('bad')"
        >
          踩
        </button>
        <button class="btn-detail btn-pulse" type="button" @click="handleDetail">查看详情</button>
        <button
          class="btn-add btn-pulse"
          type="button"
          :disabled="alreadyAdded"
          @click="handleAdd"
        >
          {{ alreadyAdded ? '已添加' : '添加到食谱' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.result-card {
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: row;
  padding: 20px;
  gap: 20px;
}
.result-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-hover);
}
.result-card-visual {
  width: 96px;
  height: 96px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(145deg, #FFF8F0 0%, #F5EDE4 100%);
  padding: 6px;
  box-sizing: border-box;
  overflow: hidden;
}
.result-card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}
.result-card-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.result-card-name {
  font-family: var(--font-title);
  font-size: 22px;
  font-weight: 500;
  color: var(--title);
  line-height: 1.35;
  white-space: normal;
  word-break: break-word;
  flex: 1;
}
.result-card-desc {
  font-size: 14px;
  color: var(--body);
  line-height: 1.6;
}
.result-card-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.result-card-meta span {
  font-size: 12px;
  color: var(--secondary);
  background: var(--bg);
  padding: 3px 8px;
  border-radius: 4px;
}
.result-card-actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
  align-items: center;
  flex-wrap: wrap;
}
.btn-change {
  padding: 8px 18px;
  background: var(--bg);
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--body);
  cursor: pointer;
  transition: all 0.2s;
  font-family: var(--font-body);
  text-align: center;
  font-weight: 500;
}
.btn-change:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.btn-fb {
  min-width: 40px;
  padding: 8px 10px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  background: #fff;
  font-size: 13px;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.2s;
  color: var(--body);
}
.btn-fb:disabled:not(.active) {
  opacity: 0.55;
  cursor: default;
}
.btn-fb-good.active {
  background: #2e7d32;
  border-color: #2e7d32;
  color: #fff;
}
.btn-fb-bad.active {
  background: #c62828;
  border-color: #c62828;
  color: #fff;
}
.btn-detail {
  padding: 8px 18px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: white;
  cursor: pointer;
  transition: background 0.2s;
  font-family: var(--font-body);
  text-align: center;
  font-weight: 500;
}
.btn-detail:hover {
  background: var(--accent-dark);
}
.btn-add {
  padding: 8px 18px;
  background: #fff;
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--accent);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
  font-family: var(--font-body);
  text-align: center;
  font-weight: 500;
}
.btn-add:hover:not(:disabled) {
  background: var(--accent);
  color: #fff;
}
.btn-add:disabled {
  opacity: 0.55;
  cursor: default;
  border-color: var(--divider);
  color: var(--secondary);
}

@media (max-width: 640px) {
  .result-card {
    flex-direction: column;
    align-items: center;
  }
  .result-card-actions {
    flex-wrap: wrap;
    justify-content: center;
  }
}
</style>
