<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useSessionStore } from '../stores/session'
import {
  parseIntent,
  recommend,
  getRandom,
  generateRecipe,
} from '../api/client'
import type { RecommendItem } from '../api/client'
import DailyRecommendations from '../components/DailyRecommendations.vue'
import MyRecipes from '../components/MyRecipes.vue'
import RecognizedTags from '../components/RecognizedTags.vue'
import FilterPanel from '../components/FilterPanel.vue'
import RecommendationCard from '../components/RecommendationCard.vue'
import ChatPanel from '../components/ChatPanel.vue'

const store = useSessionStore()

// ===== Chat state =====
interface ChatMsg { role: 'user' | 'ai'; text: string }
const chatHistory = ref<ChatMsg[]>([])
const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const sending = ref(false)
const searchedOnce = ref(false)
const showDetail = ref(false)
const detailLoading = ref(false)

const emptyTip = '哎呀，厨房暂时没存货啦，换个条件试试？'

// ===== Auto-resize textarea =====
function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

// ===== Send: parse intent → recommend =====
async function handleSend() {
  const text = inputText.value.trim()
  if (!text) {
    handleSpark()
    return
  }

  // Push user message
  chatHistory.value.push({ role: 'user', text })
  inputText.value = ''
  await nextTick()
  autoResize()

  sending.value = true
  store.loading = true

  try {
    // 1. Parse intent
    const parsed = await parseIntent(text)
    store.lastIntentText = text
    store.applyParsedIntent(parsed)

    // 2. Recommend
    const resp = await recommend(store.queryText || text, store.filters, 5)
    store.setRecommendations(resp.items, resp.message)
    searchedOnce.value = true

    // 3. AI reply
    const tagParts = store.recognizedTags.map(t => `${t.value}`)
    if (!resp.count) {
      chatHistory.value.push({ role: 'ai', text: emptyTip })
    } else {
      const guess = tagParts.length
        ? `👀 我猜你想吃：${tagParts.join(' + ')}，对吧？`
        : ''
      const found = `✨ 为你找到 ${resp.count} 道合拍的小菜`
      chatHistory.value.push({
        role: 'ai',
        text: guess ? `${guess}<br>${found}` : found,
      })
    }
  } catch (err) {
    chatHistory.value.push({ role: 'ai', text: '搜索出了点问题，请重试 😢' })
    console.error(err)
  } finally {
    sending.value = false
    store.loading = false
  }
}

// ===== Spark: random recipe =====
async function handleSpark() {
  chatHistory.value.push({ role: 'user', text: '🎲 没主意了？点我！' })
  sending.value = true
  store.loading = true

  try {
    const item = await getRandom()
    store.setRecommendations([item], '随机惊喜推荐')
    store.recognizedTags = []
    searchedOnce.value = true
    chatHistory.value.push({ role: 'ai', text: `来一道「${item.title}」试试？` })
  } catch (err) {
    chatHistory.value.push({ role: 'ai', text: '随机推荐暂时不可用，稍后再试呀' })
    console.error(err)
  } finally {
    sending.value = false
    store.loading = false
  }
}

// ===== Today card click → fill input + send =====
function handleTodaySelect(dishName: string) {
  inputText.value = `我想吃${dishName}`
  handleSend()
}

// ===== Change one: exclude current, re-recommend =====
async function handleChangeOne() {
  if (store.recommendations.length === 0) return
  // Exclude all current items
  store.recommendations.forEach(item => {
    if (item.id) store.addExcludedId(item.id)
  })

  store.loading = true
  try {
    const queryText = store.queryText || store.lastIntentText || ''
    const resp = await recommend(queryText, store.filters, 5)
    // Filter out excluded IDs
    const fresh = resp.items.filter(i => !store.excludedIds.includes(i.id))
    if (fresh.length > 0) {
      store.setRecommendations(fresh, resp.message)
    } else {
      // No new items, just show what we have
      store.setRecommendations(resp.items, '没有更多了，这些也不错 👇')
    }
  } catch (err) {
    console.error(err)
  } finally {
    store.loading = false
  }
}

// ===== View detail: SSE generate full recipe =====
async function handleDetail(item: RecommendItem) {
  showDetail.value = true
  detailLoading.value = true
  store.recipeContent = ''
  store.sources = []

  try {
    const formData = {
      mood: store.filterForm.mood || '',
      taste: store.filterForm.taste || [],
      spice_level: store.filterForm.spice_level || 0,
      servings: store.filterForm.servings || 2,
      cook_time: store.filterForm.cook_time || '',
      health_goal: store.filterForm.health_goal || '',
      ingredients: store.filterForm.ingredients || [],
      city: store.filterForm.city || '苏州',
      free_text: item.title,
    }

    for await (const evt of generateRecipe(formData)) {
      if (evt.event === 'session') {
        store.setSession(evt.data.session_id as string)
      }
      if (evt.event === 'sources') {
        store.setSources(evt.data.recipes as never[])
      }
      if (evt.event === 'recipe_chunk') {
        store.appendContent(evt.data.content as string)
      }
    }
  } catch (err) {
    store.recipeContent = '生成失败，请重试 😢'
    console.error(err)
  } finally {
    detailLoading.value = false
  }
}

// ===== Remove tag → re-recommend =====
async function handleTagRemoved() {
  if (!store.queryText && !store.lastIntentText) return
  store.loading = true
  try {
    const queryText = store.queryText || store.lastIntentText
    const resp = await recommend(queryText, store.filters, 5)
    store.setRecommendations(resp.items, resp.message)
  } catch (err) {
    console.error(err)
  } finally {
    store.loading = false
  }
}

// Watch tag removal and re-recommend — only when tag count decreases (user removed a tag)
watch(() => store.recognizedTags.length, (newLen, oldLen) => {
  if (newLen < oldLen && store.lastIntentText) {
    handleTagRemoved()
  }
})

// ===== Enter to send =====
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// ===== Reset =====
function resetAll() {
  store.recognizedTags = []
  store.recommendations = []
  store.filters = {}
  store.filterForm = {
    mood: '',
    taste: [],
    spice_level: 0,
    servings: 2,
    cook_time: '',
    health_goal: '无',
    ingredients: [],
    city: '苏州',
    free_text: '',
  }
  store.excludedIds = []
  store.queryText = ''
  store.lastIntentText = ''
  store.recommendMessage = ''
  searchedOnce.value = false
  chatHistory.value = []
  inputText.value = ''
}

// ===== Simple markdown for detail content =====
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

// ===== Scroll chat to bottom =====
const chatHistoryRef = ref<HTMLDivElement | null>(null)
watch(chatHistory, () => {
  nextTick(() => {
    if (chatHistoryRef.value) {
      chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight
    }
  })
}, { deep: true })
</script>

<template>
  <!-- Hero -->
  <div class="hero">
    <h1>今天吃什么？</h1>
    <p>直接聊聊，让食刻陪你挑一道合拍的小菜</p>
  </div>

  <!-- 今日推荐横向滚动 -->
  <DailyRecommendations @select="handleTodaySelect" />

  <!-- 我的食谱 -->
  <MyRecipes @detail="handleDetail" />

  <!-- 对话交互区（视觉焦点） -->
  <div class="chat-section">
    <div class="chat-title">直接告诉我你想吃什么</div>
    <div class="chat-hint">描述你的状态，我会自动识别并填好筛选条件</div>

    <!-- 对话历史 -->
    <div v-if="chatHistory.length" class="chat-history" ref="chatHistoryRef">
      <div
        v-for="(msg, i) in chatHistory"
        :key="i"
        class="chat-bubble"
        :class="msg.role"
        v-html="msg.text"
      />
    </div>

    <!-- 输入框 -->
    <textarea
      ref="inputRef"
      class="chat-input"
      v-model="inputText"
      placeholder="今天想吃什么呀？告诉我你的状态～"
      rows="1"
      @input="autoResize"
      @keydown="onKeydown"
    />

    <!-- 按钮行 -->
    <div class="chat-button-row">
      <button class="btn-send btn-pulse" :disabled="sending" @click="handleSend">
        {{ sending ? '搜索中…' : '发送' }}
      </button>
      <button class="btn-spark btn-pulse" :disabled="sending" @click="handleSpark">
        <span>🎲 没主意了？点我！</span>
      </button>
      <button class="btn-reset-chat btn-pulse" type="button" @click="resetAll">重置</button>
    </div>

    <!-- 已识别标签展示区 -->
    <RecognizedTags />
  </div>

  <!-- 推荐结果 + 筛选条件 左右并排 -->
  <div class="split-row">
    <div class="split-main">
      <div v-if="store.hasResults" class="results-section">
        <div class="results-header">
          <div class="section-title">✨ 为你找到 {{ store.recommendations.length }} 道合拍的小菜</div>
          <div v-if="store.recommendMessage" class="results-hint">{{ store.recommendMessage }}</div>
        </div>
        <div v-if="store.loading" class="results-loading">加载中…</div>
        <template v-else>
          <RecommendationCard
            v-for="(item, idx) in store.recommendations"
            :key="item.id"
            :item="item"
            :style="{ animationDelay: `${idx * 0.05}s` }"
            @change="handleChangeOne"
            @detail="handleDetail"
          />
        </template>
      </div>

      <div v-else class="results-panel">
        <div class="results-panel-title">推荐菜谱</div>
        <div class="results-panel-body">
          <template v-if="store.loading">加载中…</template>
          <template v-else-if="searchedOnce">{{ emptyTip }}</template>
        </div>
      </div>
    </div>

    <aside class="split-side">
      <div class="filter-section">
        <div class="filter-side-title">筛选条件</div>
        <FilterPanel side />
      </div>
    </aside>
  </div>

  <!-- 详情弹窗 -->
  <Teleport to="body">
    <div v-if="showDetail" class="detail-overlay" @click.self="showDetail = false">
      <div class="detail-modal">
        <div class="detail-header">
          <h2>📋 食谱详情</h2>
          <button class="detail-close" @click="showDetail = false">✕</button>
        </div>
        <div class="detail-body">
          <div v-if="detailLoading" class="detail-loading">正在生成食谱…</div>
          <div v-else class="recipe-content" v-html="simpleMarkdown(store.recipeContent)" />

          <!-- 对话微调面板 -->
          <ChatPanel v-if="store.sessionId && !detailLoading" :session-id="store.sessionId" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ===== Hero ===== */
.hero {
  text-align: center;
  margin-bottom: 36px;
}
.hero h1 {
  font-family: var(--font-title);
  font-size: 48px;
  font-weight: 300;
  color: var(--title);
  margin-bottom: 12px;
  line-height: 1.3;
}
.hero p {
  font-size: 16px;
  color: var(--secondary);
  max-width: 480px;
  margin: 0 auto;
}

/* ===== Chat section ===== */
.chat-section {
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: 28px;
  margin-bottom: 24px;
}
.chat-title {
  font-family: var(--font-title);
  font-size: 18px;
  font-weight: 600;
  color: var(--title);
  margin-bottom: 8px;
}
.chat-hint {
  font-size: 13px;
  color: var(--secondary);
  margin-bottom: 18px;
}
.chat-history {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 18px;
  max-height: 300px;
  overflow-y: auto;
}
.chat-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.chat-bubble.user {
  align-self: flex-end;
  background: var(--accent);
  color: white;
  border-bottom-right-radius: 4px;
}
.chat-bubble.ai {
  align-self: flex-start;
  background: var(--accent-light);
  color: var(--body);
  border: 1px solid rgba(230, 126, 34, 0.2);
  border-bottom-left-radius: 4px;
}

.chat-input {
  width: 100%;
  min-height: 56px;
  max-height: 120px;
  padding: 12px 16px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  font-size: 15px;
  font-family: var(--font-body);
  color: var(--body);
  background: var(--bg);
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  line-height: 1.5;
  margin-bottom: 12px;
}
.chat-input:focus {
  border-color: var(--accent);
}
.chat-input::placeholder {
  color: var(--secondary);
}

.chat-button-row {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}
.btn-send {
  flex: 1;
  height: 44px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 500;
  font-family: var(--font-body);
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
  box-shadow: 0 4px 14px rgba(230, 126, 34, 0.25);
}
.btn-send:hover {
  background: var(--accent-dark);
}
.btn-send:active {
  transform: scale(0.98);
}
.btn-send:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-spark {
  flex: 1;
  height: 44px;
  background: var(--bg);
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  font-family: var(--font-body);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s, transform 0.1s;
  white-space: nowrap;
}
.btn-spark:hover {
  background: var(--accent-light);
}
.btn-spark:active {
  transform: scale(0.98);
}
.btn-spark:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-reset-chat {
  flex: 0 0 auto;
  height: 44px;
  padding: 0 18px;
  background: transparent;
  color: var(--secondary);
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.2s, transform 0.1s;
  white-space: nowrap;
}
.btn-reset-chat:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
}
.btn-reset-chat:active {
  transform: scale(0.98);
}

/* ===== 推荐 + 筛选 左右布局 ===== */
.split-row {
  display: flex;
  align-items: stretch;
  gap: 20px;
  margin-top: 8px;
  margin-bottom: 24px;
}
.split-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.split-side {
  flex: 0 0 300px;
  width: 300px;
  display: flex;
  flex-direction: column;
}
.results-section {
  margin-top: 0;
  margin-bottom: 0;
  width: 100%;
}
.results-panel {
  flex: 1;
  width: 100%;
  min-height: 100%;
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: 16px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}
.results-panel-title {
  font-family: var(--font-title);
  font-size: 18px;
  font-weight: 600;
  color: var(--title);
  margin-bottom: 12px;
}
.results-panel-body {
  flex: 1;
  color: var(--secondary);
  font-size: 14px;
  line-height: 1.6;
}
.filter-section {
  flex: 1;
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: 16px;
  position: sticky;
  top: 20px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
  box-sizing: border-box;
}
.filter-side-title {
  font-family: var(--font-title);
  font-size: 18px;
  font-weight: 600;
  color: var(--title);
  margin-bottom: 12px;
}
.results-header {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 16px;
}
.results-header .section-title {
  font-family: var(--font-title);
  font-size: 20px;
  font-weight: 600;
  color: var(--title);
  display: flex;
  align-items: center;
  gap: 8px;
}
.results-hint {
  font-size: 13px;
  color: var(--secondary);
  line-height: 1.4;
}
.results-loading {
  text-align: center;
  padding: 40px;
  color: var(--secondary);
}

/* ===== Detail modal ===== */
.detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(61, 46, 34, 0.5);
  backdrop-filter: blur(4px);
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
  padding: 20px 24px;
  border-bottom: 1px solid var(--divider);
}
.detail-header h2 {
  font-family: var(--font-title);
  font-size: 20px;
  color: var(--title);
}
.detail-close {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--secondary);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}
.detail-close:hover {
  background: var(--bg);
}
.detail-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}
.detail-loading {
  text-align: center;
  padding: 40px;
  color: var(--secondary);
}
.recipe-content {
  white-space: normal;
  line-height: 1.8;
  font-size: 14px;
  color: var(--body);
}
.recipe-content h1,
.recipe-content h2,
.recipe-content h3 {
  margin: 16px 0 8px;
  color: var(--title);
  font-family: var(--font-title);
}
.recipe-content ul {
  margin: 8px 0;
  padding-left: 20px;
}
.recipe-content li {
  margin-bottom: 4px;
}

@media (max-width: 900px) {
  .split-row {
    flex-direction: column;
  }
  .split-side {
    flex: none;
    width: 100%;
  }
  .filter-section {
    position: static;
    max-height: none;
  }
  .results-panel {
    min-height: 200px;
  }
}
@media (max-width: 640px) {
  .hero h1 {
    font-size: 32px;
  }
  .chat-section {
    padding: 20px;
  }
}
</style>
