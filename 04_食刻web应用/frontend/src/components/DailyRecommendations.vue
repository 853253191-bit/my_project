<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getDailyRecommendations, timeLabel } from '../api/client'
import type { DailyItem, RecommendItem } from '../api/client'
import { useSessionStore } from '../stores/session'
import RecipeFoodIcon from './RecipeFoodIcon.vue'

const emit = defineEmits<{ (e: 'select', dishName: string): void }>()
const store = useSessionStore()

const items = ref<DailyItem[]>([])
const loading = ref(false)
const animKey = ref(0)
const refreshClicks = ref(0)
const showParty = ref(false)
const partyPieces = ref<Array<{ id: number; left: string; delay: string }>>([])
const secretDish = ref<DailyItem | null>(null)
const paused = ref(false)

const SECRET_DISHES: DailyItem[] = [
  { id: 'secret_1', title: '隐藏款・星星炒饭', decision_summary: '点满好运的神秘小炒', cuisine_main: '家常', estimated_time: 15 },
  { id: 'secret_2', title: '隐藏款・云朵蒸蛋', decision_summary: '软乎乎的治愈早餐', cuisine_main: '家常', estimated_time: 10 },
  { id: 'secret_3', title: '隐藏款・彩虹沙拉', decision_summary: '心情变好的一盘颜色', cuisine_main: '西式', estimated_time: 12 },
]

const fallbackItems: DailyItem[] = [
  { id: '1', title: '番茄蛋花汤', decision_summary: '快手暖胃汤', cuisine_main: '家常', estimated_time: 10 },
  { id: '2', title: '红烧肉', decision_summary: '经典酱香', cuisine_main: '家常', estimated_time: 60 },
  { id: '3', title: '蒜蓉西兰花', decision_summary: '清爽蒜香', cuisine_main: '家常', estimated_time: 10 },
  { id: '4', title: '麻婆豆腐', decision_summary: '麻辣下饭', cuisine_main: '川菜', estimated_time: 20 },
  { id: '5', title: '清蒸鲈鱼', decision_summary: '鲜嫩原味', cuisine_main: '粤菜', estimated_time: 20 },
  { id: '6', title: '宫保鸡丁', decision_summary: '经典下饭', cuisine_main: '川菜', estimated_time: 25 },
  { id: '7', title: '清炒时蔬', decision_summary: '清淡快手', cuisine_main: '家常', estimated_time: 10 },
  { id: '8', title: '酸辣土豆丝', decision_summary: '开胃小菜', cuisine_main: '家常', estimated_time: 15 },
]

/** 复制一份用于无缝循环滚动 */
const loopItems = computed(() => {
  if (!items.value.length) return []
  return [...items.value, ...items.value]
})

function shuffleFallback(limit = 5): DailyItem[] {
  const copy = [...fallbackItems]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy.slice(0, limit)
}

async function loadDaily() {
  if (loading.value) return
  loading.value = true
  try {
    const resp = await getDailyRecommendations(5)
    items.value = resp.items?.length ? resp.items : shuffleFallback(5)
  } catch {
    items.value = shuffleFallback(5)
  } finally {
    loading.value = false
    animKey.value += 1
  }
}

function triggerParty() {
  const secret = SECRET_DISHES[Math.floor(Math.random() * SECRET_DISHES.length)]
  secretDish.value = secret
  partyPieces.value = Array.from({ length: 18 }, (_, i) => ({
    id: i,
    left: `${6 + Math.random() * 88}%`,
    delay: `${Math.random() * 0.6}s`,
  }))
  showParty.value = true
  window.setTimeout(() => {
    showParty.value = false
  }, 2600)
}

async function handleRefresh() {
  refreshClicks.value += 1
  if (refreshClicks.value > 0 && refreshClicks.value % 5 === 0) {
    triggerParty()
  }
  await loadDaily()
}

function handleClick(item: DailyItem) {
  emit('select', item.title)
}

/** DailyItem 转为收藏所需的 RecommendItem */
function toRecommendItem(item: DailyItem): RecommendItem {
  return {
    id: item.id,
    title: item.title,
    decision_summary: item.decision_summary,
    cuisine_main: item.cuisine_main,
    estimated_time: item.estimated_time,
    ai_difficulty: item.ai_difficulty,
    image_url: item.image_url,
    ingredients: item.ingredients,
  }
}

function isAdded(item: DailyItem): boolean {
  return store.isInMyRecipes(item.id)
}

function handleAdd(item: DailyItem, e: Event) {
  e.stopPropagation()
  store.addToMyRecipes(toRecommendItem(item))
}

function handleSecretClick() {
  if (!secretDish.value) return
  emit('select', secretDish.value.title)
  showParty.value = false
}

onMounted(() => {
  loadDaily()
})
</script>

<template>
  <div class="today-section">
    <div class="section-header">
      <div class="section-title">今日主厨精选</div>
      <div class="section-actions">
        <span class="section-hint">点击卡片直接搜索</span>
        <button
          class="btn-refresh btn-pulse"
          type="button"
          :disabled="loading"
          @click="handleRefresh"
        >
          {{ loading ? '加载中…' : '换一批' }}
        </button>
      </div>
    </div>

    <!-- 与下方区块同宽：overflow 裁切，内部从右往左循环滚动 -->
    <div
      class="today-marquee"
      :class="{ 'is-loading': loading }"
      @mouseenter="paused = true"
      @mouseleave="paused = false"
    >
      <div
        class="today-track"
        :class="{ paused }"
        :key="animKey"
      >
        <div
          v-for="(item, idx) in loopItems"
          :key="`${item.id}-${idx}`"
          class="today-card"
          role="button"
          tabindex="0"
          @click="handleClick(item)"
          @keydown.enter="handleClick(item)"
        >
          <div class="today-card-art">
            <RecipeFoodIcon :title="item.title" :ingredients="item.ingredients" />
          </div>
          <div class="today-card-body">
            <button
              class="btn-add-recipe"
              type="button"
              :disabled="isAdded(item)"
              @click="handleAdd(item, $event)"
            >
              {{ isAdded(item) ? '已添加' : '添加到食谱' }}
            </button>
            <div class="today-card-name">{{ item.title }}</div>
            <div class="today-card-tags">
              <span v-if="item.estimated_time" class="today-card-tag">{{ timeLabel(item.estimated_time) }}</span>
              <span v-if="item.cuisine_main" class="today-card-tag">{{ item.cuisine_main }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showParty" class="party-layer" aria-hidden="true">
      <span
        v-for="p in partyPieces"
        :key="p.id"
        class="party-piece"
        :style="{ left: p.left, animationDelay: p.delay }"
      >🎉</span>
      <div v-if="secretDish" class="secret-wrap">
        <button
          type="button"
          class="secret-card anim-bounce-in"
          @click="handleSecretClick"
        >
          <div class="secret-badge">隐藏菜谱</div>
          <div class="secret-title">{{ secretDish.title }}</div>
          <div class="secret-desc">{{ secretDish.decision_summary }}</div>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.today-section {
  position: relative;
  margin-bottom: 36px;
  width: 100%;
  box-sizing: border-box;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}
.section-title {
  font-family: var(--font-title);
  font-size: 20px;
  font-weight: 600;
  color: var(--title);
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.section-hint {
  font-size: 13px;
  color: var(--secondary);
}
.btn-refresh {
  padding: 6px 14px;
  font-size: 13px;
  font-family: var(--font-body);
  font-weight: 500;
  color: var(--accent);
  background: var(--bg);
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}
.btn-refresh:hover:not(:disabled) {
  border-color: var(--accent);
  background: #fff;
}
.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 与下方「我的食谱 / 对话区」同宽对齐 */
.today-marquee {
  width: 100%;
  overflow: hidden;
  box-sizing: border-box;
  border-radius: var(--radius-lg);
  background: var(--card);
  box-shadow: var(--shadow);
  padding: 16px 0;
  transition: opacity 0.2s;
}
.today-marquee.is-loading {
  opacity: 0.55;
  pointer-events: none;
}
.today-track {
  display: flex;
  align-items: stretch;
  width: max-content;
  animation: marquee-rtl 28s linear infinite;
  will-change: transform;
}
.today-track.paused {
  animation-play-state: paused;
}

@keyframes marquee-rtl {
  from {
    transform: translateX(0);
  }
  to {
    /* 列表复制了一份；每张卡含右边距，-50% 正好对齐接缝 */
    transform: translateX(-50%);
  }
}

.today-card {
  flex-shrink: 0;
  width: 176px;
  margin-right: 14px;
  background: var(--bg);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow);
  cursor: pointer;
  transition: box-shadow 0.2s;
  border: none;
  text-align: left;
  font-family: var(--font-body);
  padding: 0;
  display: flex;
  flex-direction: column;
}
.today-card:hover {
  box-shadow: var(--shadow-hover);
}
.today-card-art {
  width: 100%;
  height: 100px;
  flex-shrink: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.today-card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 10px 12px 12px;
  background: #fff;
  gap: 6px;
}
/* 图标正下方：添加到我的食谱 */
.btn-add-recipe {
  width: 100%;
  padding: 5px 8px;
  font-size: 12px;
  font-family: var(--font-body);
  font-weight: 500;
  color: var(--accent);
  background: #fff;
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
  flex-shrink: 0;
}
.btn-add-recipe:hover:not(:disabled) {
  background: var(--accent);
  color: #fff;
}
.btn-add-recipe:disabled {
  opacity: 0.55;
  cursor: default;
  border-color: var(--divider);
  color: var(--secondary);
}
.today-card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--title);
  line-height: 1.4;
  min-height: calc(1.4em * 2);
  white-space: normal;
  overflow: visible;
  word-break: break-word;
}
.today-card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: auto;
}
.today-card-tag {
  font-size: 11px;
  color: var(--secondary);
  background: var(--bg);
  padding: 2px 6px;
  border-radius: 4px;
}

.party-layer {
  pointer-events: none;
  position: absolute;
  inset: 0;
  overflow: hidden;
  z-index: 5;
}
.party-piece {
  position: absolute;
  top: -8px;
  font-size: 18px;
  animation: confetti-fall 2.2s ease-in forwards;
}
.secret-wrap {
  pointer-events: auto;
  position: absolute;
  left: 50%;
  top: 42%;
  transform: translate(-50%, -50%);
  width: min(320px, 86%);
}
.secret-card {
  width: 100%;
  padding: 16px 18px;
  border: none;
  border-radius: var(--radius-md);
  background: #fff;
  box-shadow: var(--shadow-hover);
  text-align: left;
  cursor: pointer;
  font-family: var(--font-body);
}
.secret-badge {
  display: inline-block;
  font-size: 11px;
  color: #fff;
  background: var(--accent);
  border-radius: 999px;
  padding: 2px 8px;
  margin-bottom: 8px;
}
.secret-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--title);
  margin-bottom: 4px;
}
.secret-desc {
  font-size: 13px;
  color: var(--secondary);
}

@media (max-width: 640px) {
  .section-hint {
    display: none;
  }
  .today-track {
    animation-duration: 22s;
  }
}

@media (prefers-reduced-motion: reduce) {
  .today-track {
    animation: none;
  }
}
</style>
