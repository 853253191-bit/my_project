<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch } from '../utils/request'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{
  recipeId: string
  initialFavorited?: boolean
  size?: 'sm' | 'md'
}>()

const emit = defineEmits<{
  (e: 'change', favorited: boolean): void
}>()

const auth = useAuthStore()
const router = useRouter()
const favorited = ref(!!props.initialFavorited)
const busy = ref(false)
const beating = ref(false)

watch(
  () => props.initialFavorited,
  (v) => {
    favorited.value = !!v
  },
)

const label = computed(() => (favorited.value ? '已收藏' : '收藏'))

function triggerBeat() {
  beating.value = true
  window.setTimeout(() => {
    beating.value = false
  }, 420)
}

async function toggle() {
  if (!props.recipeId) return
  if (!auth.isLoggedIn) {
    router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    return
  }
  if (busy.value) return
  busy.value = true
  try {
    if (favorited.value) {
      await apiFetch(`/api/favorites/${encodeURIComponent(props.recipeId)}`, {
        method: 'DELETE',
      })
      favorited.value = false
    } else {
      await apiFetch('/api/favorites', {
        method: 'POST',
        json: { recipe_id: props.recipeId },
      })
      favorited.value = true
      triggerBeat()
    }
    emit('change', favorited.value)
  } catch (err) {
    console.error(err)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  if (!auth.isLoggedIn || !props.recipeId || props.initialFavorited !== undefined) return
  try {
    const data = await apiFetch<{ is_favorited: boolean }>(
      `/api/favorites/check/${encodeURIComponent(props.recipeId)}`,
    )
    favorited.value = !!data.is_favorited
  } catch {
    /* ignore */
  }
})
</script>

<template>
  <button
    type="button"
    class="fav-btn"
    :class="[size || 'md', { on: favorited }]"
    :disabled="busy"
    :title="label"
    @click.stop="toggle"
  >
    <span class="fav-icon" :class="{ beat: beating }" aria-hidden="true">{{ favorited ? '❤️' : '🤍' }}</span>
    <span class="fav-text">{{ label }}</span>
  </button>
</template>

<style scoped>
.fav-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #d0c4b8;
  background: #fff;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font-body);
  color: #9b8b7d;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
  flex-shrink: 0;
  font-weight: 600;
}
.fav-btn.md {
  padding: 8px 14px;
  font-size: 14px;
}
.fav-btn.sm {
  padding: 6px 10px;
  font-size: 13px;
}
.fav-btn:hover:not(:disabled) {
  border-color: #e74c3c;
  color: #e74c3c;
  background: #fff5f5;
}
.fav-btn.on {
  border-color: #e74c3c;
  color: #e74c3c;
  background: #fff5f5;
}
.fav-icon {
  font-size: 16px;
  line-height: 1;
  display: inline-block;
  transform-origin: center;
}
.fav-icon.beat {
  animation: heart-beat 0.42s ease;
}
@keyframes heart-beat {
  0% {
    transform: scale(1);
  }
  40% {
    transform: scale(1.3);
  }
  100% {
    transform: scale(1);
  }
}
.fav-btn:disabled {
  opacity: 0.55;
  cursor: default;
}
</style>
