<template>
  <div class="chat-panel card">
    <h3>对话微调</h3>
    <p class="chat-hint">对食谱不满意？告诉我你想怎么调整</p>

    <div class="quick-actions">
      <button v-for="q in quickActions" :key="q" @click="send(q)">{{ q }}</button>
    </div>

    <div class="chat-input-row">
      <input
        v-model="message"
        type="text"
        placeholder="例如：换成不辣的、更简单一些"
        @keyup.enter="send(message)"
      />
      <button class="btn btn-primary" :disabled="!message.trim() || loading" @click="send(message)">
        发送
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { chatRecipe } from '../api/client'
import { useSessionStore } from '../stores/session'

const props = defineProps<{
  sessionId: string
}>()

const emit = defineEmits<{
  updated: []
}>()

const store = useSessionStore()
const message = ref('')
const loading = ref(false)

const quickActions = ['换一道', '不要辣', '更简单', '缩短时间', '换成素食']

async function send(text: string) {
  if (!text.trim() || loading.value) return
  loading.value = true
  message.value = ''

  store.recipeContent = ''

  try {
    for await (const evt of chatRecipe(props.sessionId, text.trim())) {
      if (evt.event === 'sources') {
        store.setSources(evt.data.recipes as never[])
      }
      if (evt.event === 'recipe_chunk') {
        store.appendContent(evt.data.content as string)
      }
    }
    emit('updated')
  } catch (err) {
    alert('对话失败，请重试')
    console.error(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.chat-panel {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--divider);
}
.chat-panel h3 {
  font-family: var(--font-title);
  font-size: 16px;
  color: var(--title);
  margin-bottom: 4px;
}
.chat-hint {
  color: var(--secondary);
  font-size: 13px;
  margin-bottom: 12px;
}
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.quick-actions button {
  padding: 6px 14px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  background: var(--card);
  color: var(--body);
  font-size: 13px;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.15s;
}
.quick-actions button:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.chat-input-row {
  display: flex;
  gap: 8px;
}
.chat-input-row input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--body);
  background: var(--bg);
  outline: none;
  font-family: var(--font-body);
  transition: border-color 0.2s;
}
.chat-input-row input:focus {
  border-color: var(--accent);
}
</style>
