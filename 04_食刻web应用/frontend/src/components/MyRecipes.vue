<script setup lang="ts">
import { useSessionStore } from '../stores/session'
import { timeLabel } from '../api/client'
import type { RecommendItem } from '../api/client'
import RecipeFoodIcon from './RecipeFoodIcon.vue'

const store = useSessionStore()

const emit = defineEmits<{
  (e: 'detail', item: RecommendItem): void
}>()

function handleDetail(item: RecommendItem) {
  emit('detail', item)
}

function handleRemove(id: string, e: Event) {
  e.stopPropagation()
  store.removeFromMyRecipes(id)
}

function handleClear() {
  if (!store.myRecipes.length) return
  if (window.confirm('确定清空我的食谱吗？')) {
    store.clearMyRecipes()
  }
}
</script>

<template>
  <div class="my-recipes-section">
    <div class="section-header">
      <div class="section-title">
        我的食谱
        <span class="section-count">{{ store.myRecipes.length }}</span>
      </div>
      <div class="section-actions">
        <button
          v-if="store.hasMyRecipes"
          class="btn-clear"
          type="button"
          @click="handleClear"
        >
          清空
        </button>
      </div>
    </div>

    <div v-if="!store.hasMyRecipes" class="my-recipes-empty">
      还没有添加菜谱，在推荐结果里点「添加到食谱」即可收藏
    </div>

    <div v-else class="my-recipes-scroll">
      <div
        v-for="item in store.myRecipes"
        :key="item.id"
        class="my-card"
        role="button"
        tabindex="0"
        @click="handleDetail(item)"
        @keydown.enter="handleDetail(item)"
      >
        <div class="my-card-art">
          <RecipeFoodIcon :title="item.title" :ingredients="item.ingredients" />
        </div>
        <div class="my-card-body">
          <div class="my-card-name">{{ item.title }}</div>
          <div class="my-card-tags">
            <span v-if="item.estimated_time" class="my-card-tag">{{ timeLabel(item.estimated_time) }}</span>
            <span v-if="item.cuisine_main" class="my-card-tag">{{ item.cuisine_main }}</span>
          </div>
        </div>
        <button
          class="btn-remove"
          type="button"
          title="移除"
          @click="handleRemove(item.id, $event)"
        >
          移除
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.my-recipes-section {
  margin-bottom: 36px;
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
.section-count {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  color: var(--secondary);
  background: var(--bg);
  padding: 2px 8px;
  border-radius: 999px;
}
.section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.btn-clear {
  padding: 6px 14px;
  font-size: 13px;
  font-family: var(--font-body);
  font-weight: 500;
  color: var(--body);
  background: var(--bg);
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.btn-clear:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.my-recipes-empty {
  padding: 20px 16px;
  background: var(--card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow);
  color: var(--secondary);
  font-size: 14px;
  line-height: 1.6;
}
.my-recipes-scroll {
  display: flex;
  align-items: stretch;
  gap: 14px;
  overflow-x: auto;
  padding: 4px 0 12px;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}
.my-recipes-scroll::-webkit-scrollbar { height: 6px; }
.my-recipes-scroll::-webkit-scrollbar-track { background: var(--divider); border-radius: 3px; }
.my-recipes-scroll::-webkit-scrollbar-thumb { background: var(--secondary); border-radius: 3px; opacity: 0.4; }

.my-card {
  position: relative;
  flex-shrink: 0;
  width: 176px;
  background: var(--card);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  border: none;
  text-align: left;
  font-family: var(--font-body);
  padding: 0;
  display: flex;
  flex-direction: column;
}
.my-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-hover);
}
.my-card-art {
  width: 100%;
  height: 100px;
  flex-shrink: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #FFF8F0 0%, #F5EDE4 100%);
}
.my-card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 10px 12px 36px;
}
.my-card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--title);
  margin-bottom: 4px;
  line-height: 1.4;
  min-height: calc(1.4em * 2);
  white-space: normal;
  overflow: visible;
  word-break: break-word;
}
.my-card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: auto;
}
.my-card-tag {
  font-size: 11px;
  color: var(--secondary);
  background: var(--bg);
  padding: 2px 6px;
  border-radius: 4px;
}
.btn-remove {
  position: absolute;
  right: 8px;
  bottom: 8px;
  padding: 4px 8px;
  font-size: 12px;
  font-family: var(--font-body);
  color: var(--secondary);
  background: var(--bg);
  border: 1px solid var(--divider);
  border-radius: 4px;
  cursor: pointer;
}
.btn-remove:hover {
  color: var(--accent);
  border-color: var(--accent);
}
</style>
