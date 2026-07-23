<template>
  <div class="card">
    <h2 class="form-title">今天想吃什么？</h2>
    <p class="form-subtitle">根据你的心情和情境，为你推荐专属食谱</p>

    <div v-if="weatherInfo" class="weather-bar">
      <span>{{ weatherInfo.city }}</span>
      <span>{{ weatherInfo.weather }}</span>
      <span>{{ weatherInfo.temperature }}</span>
    </div>

    <form @submit.prevent="onSubmit">
      <div class="form-section">
        <h3>心情</h3>
        <div class="chip-group">
          <button
            v-for="m in moods"
            :key="m"
            type="button"
            class="chip"
            :class="{ active: form.mood === m }"
            @click="form.mood = m"
          >{{ m }}</button>
        </div>
      </div>

      <div class="form-section">
        <h3>口味（可多选）</h3>
        <div class="chip-group">
          <button
            v-for="t in tastes"
            :key="t"
            type="button"
            class="chip"
            :class="{ active: form.taste.includes(t) }"
            @click="toggleTaste(t)"
          >{{ t }}</button>
        </div>
      </div>

      <div class="form-section">
        <h3>辣度：{{ spiceLabels[form.spice_level] }}</h3>
        <input v-model.number="form.spice_level" type="range" min="0" max="3" step="1" />
      </div>

      <div class="form-section form-row">
        <div>
          <h3>人数</h3>
          <input v-model.number="form.servings" type="number" min="1" max="8" />
        </div>
        <div>
          <h3>耗时</h3>
          <select v-model="form.cook_time">
            <option v-for="ct in cookTimes" :key="ct" :value="ct">{{ ct }}</option>
          </select>
        </div>
      </div>

      <div class="form-section">
        <h3>健康目标</h3>
        <div class="chip-group">
          <button
            v-for="h in healthGoals"
            :key="h"
            type="button"
            class="chip"
            :class="{ active: form.health_goal === h }"
            @click="form.health_goal = h"
          >{{ h }}</button>
        </div>
      </div>

      <div class="form-section">
        <h3>现有食材（逗号分隔）</h3>
        <input
          v-model="ingredientsText"
          type="text"
          placeholder="例如：鸡蛋, 番茄, 面条"
        />
      </div>

      <div class="form-section form-row">
        <div>
          <h3>城市（用于天气）</h3>
          <input v-model="form.city" type="text" placeholder="上海" @blur="loadWeather" />
        </div>
      </div>

      <div class="form-section">
        <h3>补充说明</h3>
        <textarea v-model="form.free_text" placeholder="例如：昨天吃太油腻了，今天想清淡点" />
      </div>

      <button type="submit" class="btn btn-primary submit-btn" :disabled="!canSubmit || loading">
        {{ loading ? '生成中...' : '生成食谱' }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchWeather, generateRecipe, type GenerateRequest, type WeatherInfo } from '../api/client'
import { useSessionStore } from '../stores/session'

const router = useRouter()
const store = useSessionStore()

const moods = ['开心', '疲惫', '想治愈', '想尝鲜']
const tastes = ['咸鲜', '酸甜', '麻辣', '清淡']
const cookTimes = ['15分钟内', '30分钟内', '1小时内', '不限']
const healthGoals = ['无', '减脂', '增肌', '控糖', '素食']
const spiceLabels = ['不辣', '微辣', '中辣', '重辣']

const loading = ref(false)
const weatherInfo = ref<WeatherInfo | null>(null)
const ingredientsText = ref('')

const form = reactive<GenerateRequest>({
  mood: '',
  taste: [],
  spice_level: 0,
  servings: 2,
  cook_time: '30分钟内',
  health_goal: '无',
  ingredients: [],
  city: '',
  free_text: '',
})

const canSubmit = computed(() => form.mood && form.taste.length > 0 && form.servings >= 1)

function toggleTaste(t: string) {
  const idx = form.taste.indexOf(t)
  if (idx >= 0) form.taste.splice(idx, 1)
  else form.taste.push(t)
}

async function loadWeather() {
  if (!form.city.trim()) return
  try {
    weatherInfo.value = await fetchWeather(form.city.trim())
  } catch {
    weatherInfo.value = null
  }
}

async function onSubmit() {
  if (!canSubmit.value) return
  loading.value = true
  store.reset()

  form.ingredients = ingredientsText.value
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)

  store.setFormData({ ...form })

  try {
    let sessionId = ''
    for await (const evt of generateRecipe({ ...form })) {
      if (evt.event === 'session' || evt.event === 'done') {
        sessionId = evt.data.session_id as string
        store.setSession(sessionId)
      }
      if (evt.event === 'sources') {
        store.setSources(evt.data.recipes as never[])
      }
      if (evt.event === 'recipe_chunk') {
        store.appendContent(evt.data.content as string)
      }
    }
    if (sessionId) {
      router.push(`/result/${sessionId}`)
    }
  } catch (err) {
    alert('生成失败，请检查后端服务是否启动')
    console.error(err)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.form-title {
  font-size: 1.5rem;
  margin-bottom: 4px;
}
.form-subtitle {
  color: var(--color-text-light);
  margin-bottom: 20px;
  font-size: 0.95rem;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.submit-btn {
  width: 100%;
  margin-top: 8px;
}
</style>
