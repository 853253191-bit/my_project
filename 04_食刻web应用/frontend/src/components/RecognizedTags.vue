<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useSessionStore } from '../stores/session'

const store = useSessionStore()
const shakingKey = ref('')

const guessText = computed(() => {
  const values = store.recognizedTags.map(t => t.value).filter(Boolean)
  if (!values.length) return ''
  return values.join(' + ')
})

async function removeTag(idx: number) {
  const tag = store.recognizedTags[idx]
  if (!tag) return
  const key = tag.field + tag.category
  shakingKey.value = key
  await new Promise(r => setTimeout(r, 320))
  store.removeTag(tag)
  await nextTick()
  shakingKey.value = ''
}
</script>

<template>
  <div v-if="store.recognizedTags.length" class="recognized-tags">
    <span class="label">👀 我猜你想吃：</span>
    <span class="guess">{{ guessText }}</span>
    <span class="ask">，对吧？</span>
    <div class="tag-list">
      <button
        v-for="(tag, idx) in store.recognizedTags"
        :key="tag.field + tag.category"
        type="button"
        class="tag"
        :class="{ shaking: shakingKey === tag.field + tag.category }"
        :title="`移除 ${tag.category}·${tag.value}`"
        @click="removeTag(idx)"
      >
        {{ tag.value }}
        <span class="x">✕</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.recognized-tags {
  margin-bottom: 12px;
  padding: 12px 14px;
  background: #FFF0E0;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(230, 126, 34, 0.15);
  font-size: 13px;
  color: #E67E22;
  line-height: 1.5;
}
.recognized-tags .label {
  font-weight: 600;
}
.recognized-tags .guess {
  font-weight: 600;
}
.recognized-tags .ask {
  color: var(--body);
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(230, 126, 34, 0.25);
  background: #fff;
  color: #E67E22;
  font-size: 12px;
  font-family: var(--font-body);
  cursor: pointer;
  transition: opacity 0.2s, transform 0.2s;
}
.tag:hover {
  opacity: 0.85;
}
.tag.shaking {
  animation: shake-tag 0.32s ease;
}
.tag .x {
  font-size: 11px;
  opacity: 0.7;
}
</style>
