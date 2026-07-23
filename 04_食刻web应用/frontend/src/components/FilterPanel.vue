<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useSessionStore } from '../stores/session'
import type { RecommendFilters } from '../api/client'

const props = withDefaults(defineProps<{ side?: boolean }>(), { side: false })

const store = useSessionStore()
const expanded = ref(props.side)

// ===== Options =====
const moodOptions = ['疲惫', '开心', '焦虑', '平静', '馋了', '慵懒']
const tasteOptions = ['咸鲜', '酸甜', '麻辣', '酸辣', '蒜香', '酱香', '咖喱', '葱香', '香辣', '清香']
const spicyOptions = ['🌱不辣', '🌶️微辣', '🔥中辣', '💀重辣']
const cuisineOptions = ['家常', '川菜', '粤菜', '湘菜', '江浙', '日料', '西餐']
const methodOptions = ['炒', '炖', '蒸', '凉拌']
const greasinessOptions = ['🧊清淡', '⚖️适中', '🫕浓郁']
const timeOptions = ['15分钟', '30分钟', '1小时', '不限']
const healthOptions = ['减脂', '增肌', '控糖', '养胃']
const allergenOptions = ['花生', '海鲜', '蛋奶', '大豆', '坚果', '无']

// ===== Local state (synced from store) =====
const mood = ref('')
const taste = ref<string[]>([])
const spicyIdx = ref(-1) // -1 = not selected
const cuisine = ref('')
const method = ref('')
const greasinessIdx = ref(-1)
const timeIdx = ref(-1)
const healthGoal = ref('')
const allergens = ref<string[]>(['无'])
const ingredientsText = ref('')
const city = ref('苏州')
/** 中文输入法组合中，暂不同步，避免标点/汉字被回写冲掉 */
const ingredientsComposing = ref(false)

/** 把食材原文拆成数组（顿号/中英文逗号/空白作分隔） */
function parseIngredients(text: string): string[] {
  return text
    .split(/[、,，\s]+/)
    .map(s => s.trim())
    .filter(Boolean)
}

// Sync from store when applyParsedIntent runs
watch(() => store.filterForm, (f) => {
  mood.value = f.mood || ''
  taste.value = f.taste ? [...f.taste] : []
  if (f.spice_level !== undefined && f.spice_level > 0) {
    spicyIdx.value = Math.min(f.spice_level - 1, 3) // 1->0, 2->1, 3->2, but we have 4 options
    // Actually spice_level in form: 0=不辣, 1=微辣, 2=中辣, 3=重辣
    // But if 0 means "not selected" then we need to adjust
    // Let's use: -1 = not selected, 0-3 = the four options
    spicyIdx.value = f.spice_level > 0 ? Math.min(f.spice_level, 3) : -1
    // Wait, the labels are: 不辣(0), 微辣(1), 中辣(2), 重辣(3)
    // If spice_level = 0, that means "不辣" which is a valid selection
    // But in our UI, -1 means "not selected". So we need a separate flag.
    // For simplicity, let's use: -1 = not selected, 0-3 = 不辣/微辣/中辣/重辣
    // And spice_level in the form: 0-3 maps directly
    // But then spice_level=0 (不辣) looks the same as "not set"
    // Solution: use a separate spicySelected boolean
  }
  healthGoal.value = f.health_goal || ''
  // 仅当 store 解析结果与当前输入语义不同时才回写，保留用户正在输入的中文标点
  const joined = (f.ingredients || []).join('、')
  const localJoined = parseIngredients(ingredientsText.value).join('、')
  if (joined !== localJoined) {
    ingredientsText.value = joined
  }
  city.value = f.city || '苏州'
}, { deep: true, immediate: true })

// Separate flag for spicy selection
const spicySelected = ref(false)
watch(() => store.filterForm, (f) => {
  spicySelected.value = f.spice_level !== undefined && f.spice_level >= 0 && f.spice_level <= 3
  if (spicySelected.value) {
    spicyIdx.value = f.spice_level ?? 0
  } else {
    spicyIdx.value = -1
  }
}, { deep: true, immediate: true })

// Sync filters from store
watch(() => store.filters, (fl) => {
  // cuisine
  cuisine.value = fl.cuisine_main || ''
  // greasiness: 1=清淡, 3=适中, 5=浓郁
  if (fl.greasiness_max === 1) greasinessIdx.value = 0
  else if (fl.greasiness_max != null && fl.greasiness_max <= 3) greasinessIdx.value = 1
  else if (fl.greasiness_max != null && fl.greasiness_max >= 4) greasinessIdx.value = 2
  else greasinessIdx.value = -1
  // time: 15->0, 30->1, 60->2, null/0->3(不限)
  if (fl.estimated_time_max === 15) timeIdx.value = 0
  else if (fl.estimated_time_max === 30) timeIdx.value = 1
  else if (fl.estimated_time_max === 60) timeIdx.value = 2
  else if (!fl.estimated_time_max) timeIdx.value = 3
  // allergens
  allergens.value = fl.exclude_allergens ? [...fl.exclude_allergens] : ['无']
}, { deep: true, immediate: true })

// ===== Toggle handlers =====
function toggleMood(opt: string) {
  mood.value = mood.value === opt ? '' : opt
  syncToStore()
}
function toggleTaste(opt: string) {
  const idx = taste.value.indexOf(opt)
  if (idx >= 0) taste.value.splice(idx, 1)
  else taste.value.push(opt)
  syncToStore()
}
function toggleSpicy(idx: number) {
  if (spicyIdx.value === idx && spicySelected.value) {
    spicySelected.value = false
    spicyIdx.value = -1
  } else {
    spicySelected.value = true
    spicyIdx.value = idx
  }
  syncToStore()
}
function toggleCuisine(opt: string) {
  cuisine.value = cuisine.value === opt ? '' : opt
  syncToStore()
}
function toggleMethod(opt: string) {
  method.value = method.value === opt ? '' : opt
  syncToStore()
}
function toggleGreasiness(idx: number) {
  if (greasinessIdx.value === idx) greasinessIdx.value = -1
  else greasinessIdx.value = idx
  syncToStore()
}
function toggleTime(idx: number) {
  if (timeIdx.value === idx) timeIdx.value = -1
  else timeIdx.value = idx
  syncToStore()
}
function toggleHealth(opt: string) {
  healthGoal.value = healthGoal.value === opt ? '' : opt
  syncToStore()
}
function toggleAllergen(opt: string) {
  if (opt === '无') {
    allergens.value = ['无']
  } else {
    allergens.value = allergens.value.filter(a => a !== '无')
    const idx = allergens.value.indexOf(opt)
    if (idx >= 0) allergens.value.splice(idx, 1)
    else allergens.value.push(opt)
    if (allergens.value.length === 0) allergens.value = ['无']
  }
  syncToStore()
}

function onIngredientsInput() {
  if (ingredientsComposing.value) return
  syncToStore()
}
function onIngredientsCompositionStart() {
  ingredientsComposing.value = true
}
function onIngredientsCompositionEnd() {
  ingredientsComposing.value = false
  syncToStore()
}
function onCityInput() {
  syncToStore()
}

// ===== Sync back to store =====
function syncToStore() {
  // Update form
  store.updateForm({
    mood: mood.value,
    taste: [...taste.value],
    spice_level: spicySelected.value ? spicyIdx.value : 0,
    health_goal: healthGoal.value,
    ingredients: parseIngredients(ingredientsText.value),
    city: city.value,
  })

  // Update filters
  const newFilters: RecommendFilters = {}
  if (cuisine.value) newFilters.cuisine_main = cuisine.value
  // greasiness mapping
  const gMap = [1, 3, 5] // 清淡=1, 适中=3, 浓郁=5
  if (greasinessIdx.value >= 0) {
    newFilters.greasiness_max = gMap[greasinessIdx.value]
  }
  // time mapping
  const tMap = [15, 30, 60, 0] // 15分钟, 30分钟, 1小时, 不限(0=null)
  if (timeIdx.value >= 0 && timeIdx.value < 3) {
    newFilters.estimated_time_max = tMap[timeIdx.value]
  }
  // allergens
  if (allergens.value.length && !allergens.value.includes('无')) {
    newFilters.exclude_allergens = [...allergens.value]
  }
  store.updateFilters(newFilters)
}

// ===== Summary for collapsed state =====
const summaryText = computed(() => {
  const parts: string[] = []
  if (mood.value) parts.push(mood.value)
  if (ingredientsText.value) parts.push(ingredientsText.value)
  if (taste.value.length) parts.push(taste.value.join('、'))
  if (cuisine.value) parts.push(cuisine.value)
  if (spicySelected.value) parts.push(spicyOptions[spicyIdx.value])
  return parts.length ? `已选：${parts.join(' | ')}` : '点击展开设置筛选条件'
})

defineExpose({ expanded })
</script>

<template>
  <div class="filter-panel" :class="{ side }">
  <!-- 折叠入口 -->
  <button
    class="filter-toggle"
    :class="{ expanded }"
    @click="expanded = !expanded"
  >
    <span class="left">
      <span class="icon">📋</span>
      <span>快速筛选</span>
      <span class="summary">{{ summaryText }}</span>
    </span>
    <span class="arrow">{{ expanded ? '收起 ↑' : '展开全部条件 →' }}</span>
  </button>

  <!-- 筛选表单（默认收起） -->
  <div class="filter-form" :class="{ expanded }">
    <!-- 心情卡片 -->
    <div class="filter-card">
      <div class="filter-card-title">😊 今天心情</div>
      <div class="filter-row">
        <span
          v-for="opt in moodOptions"
          :key="opt"
          class="filter-tag"
          :class="{ selected: mood === opt }"
          @click="toggleMood(opt)"
        >{{ opt }}</span>
      </div>
    </div>

    <!-- 口味偏好卡片 -->
    <div class="filter-card">
      <div class="filter-card-title">👅 口味偏好</div>
      <div class="filter-row">
        <span
          v-for="opt in tasteOptions.slice(0, 5)"
          :key="opt"
          class="filter-tag"
          :class="{ selected: taste.includes(opt) }"
          @click="toggleTaste(opt)"
        >{{ opt }}</span>
      </div>
      <div class="filter-row">
        <span
          v-for="opt in tasteOptions.slice(5)"
          :key="opt"
          class="filter-tag"
          :class="{ selected: taste.includes(opt) }"
          @click="toggleTaste(opt)"
        >{{ opt }}</span>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-inline-group">
        <span class="filter-label">辣度：</span>
        <span
          v-for="(opt, idx) in spicyOptions"
          :key="opt"
          class="filter-tag"
          :class="{ selected: spicySelected && spicyIdx === idx }"
          @click="toggleSpicy(idx)"
        >{{ opt }}</span>
      </div>
    </div>

    <!-- 烹饪条件卡片 -->
    <div class="filter-card">
      <div class="filter-card-title">🍳 烹饪条件</div>
      <div class="filter-label">菜系 / 做法</div>
      <div class="filter-row">
        <span
          v-for="opt in cuisineOptions"
          :key="opt"
          class="filter-tag"
          :class="{ selected: cuisine === opt }"
          @click="toggleCuisine(opt)"
        >{{ opt }}</span>
      </div>
      <div class="filter-row">
        <span
          v-for="opt in methodOptions"
          :key="opt"
          class="filter-tag"
          :class="{ selected: method === opt }"
          @click="toggleMethod(opt)"
        >{{ opt }}</span>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-two-col">
        <div>
          <div class="filter-label">油盐偏好</div>
          <div class="filter-row">
            <span
              v-for="(opt, idx) in greasinessOptions"
              :key="opt"
              class="filter-tag"
              :class="{ selected: greasinessIdx === idx }"
              @click="toggleGreasiness(idx)"
            >{{ opt }}</span>
          </div>
        </div>
        <div>
          <div class="filter-label">烹饪时间</div>
          <div class="filter-row">
            <span
              v-for="(opt, idx) in timeOptions"
              :key="opt"
              class="filter-tag"
              :class="{ selected: timeIdx === idx }"
              @click="toggleTime(idx)"
            >{{ opt }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 健康目标 + 忌口卡片 -->
    <div class="filter-card">
      <div class="filter-card-title">💊 健康目标</div>
      <div class="filter-row">
        <span
          v-for="opt in healthOptions"
          :key="opt"
          class="filter-tag"
          :class="{ selected: healthGoal === opt }"
          @click="toggleHealth(opt)"
        >{{ opt }}</span>
      </div>
      <div class="filter-divider"></div>
      <div class="filter-label">🚫 忌口 / 过敏</div>
      <div class="filter-row">
        <span
          v-for="opt in allergenOptions"
          :key="opt"
          class="filter-tag"
          :class="{ selected: allergens.includes(opt) }"
          @click="toggleAllergen(opt)"
        >{{ opt }}</span>
      </div>
    </div>

    <!-- 食材 + 城市卡片 -->
    <div class="filter-card">
      <div class="filter-card-title">🥬 食材 &amp; 城市</div>
      <div class="filter-label">现有食材</div>
      <input
        class="ingredients-input"
        type="text"
        placeholder="如：鸡蛋、番茄、豆腐…"
        v-model="ingredientsText"
        @input="onIngredientsInput"
        @compositionstart="onIngredientsCompositionStart"
        @compositionend="onIngredientsCompositionEnd"
      >
      <div class="ingredients-hint">💡 食材越全，推荐越准</div>
      <div class="filter-divider"></div>
      <div class="filter-label">📍 城市</div>
      <div class="city-input-wrapper">
        <span class="city-icon">📍</span>
        <input
          class="city-input"
          type="text"
          v-model="city"
          @input="onCityInput"
          placeholder="自动定位 / 手动修改"
        >
      </div>
    </div>
  </div>
  </div>
</template>

<style scoped>
.filter-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg);
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  color: var(--body);
  font-size: 13px;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  gap: 8px;
}
.filter-toggle:hover {
  border-color: var(--accent);
  background: var(--accent-light);
}
.filter-toggle .left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}
.filter-toggle .icon {
  color: var(--accent);
}
.filter-toggle .summary {
  color: var(--secondary);
}
.filter-toggle .arrow {
  color: var(--secondary);
  transition: transform 0.3s;
  font-size: 12px;
  flex-shrink: 0;
}

.filter-form {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.4s ease, margin-top 0.3s;
  margin-top: 0;
}
.filter-form.expanded {
  max-height: 2400px;
  margin-top: 16px;
}

.filter-panel.side .filter-card {
  padding: 14px;
  box-shadow: none;
  border: 1px solid var(--divider);
  margin-bottom: 10px;
}
.filter-panel.side .filter-toggle .summary {
  display: block;
  width: 100%;
  margin-top: 2px;
}

.filter-card {
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: 24px;
  margin-bottom: 16px;
}
.filter-card:last-child {
  margin-bottom: 0;
}
.filter-card-title {
  font-family: var(--font-title);
  font-size: 16px;
  font-weight: 600;
  color: var(--title);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.filter-row:last-child {
  margin-bottom: 0;
}
.filter-tag {
  padding: 6px 14px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--body);
  cursor: pointer;
  transition: all 0.15s;
  background: white;
  font-family: var(--font-body);
  user-select: none;
}
.filter-tag:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.filter-tag.selected {
  background: var(--accent-light);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 500;
}
.filter-label {
  font-size: 13px;
  color: var(--secondary);
  margin-bottom: 6px;
  font-weight: 500;
}
.filter-divider {
  height: 1px;
  background: var(--divider);
  margin: 14px 0;
}
.filter-inline-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.filter-inline-group .filter-label {
  margin-bottom: 0;
  white-space: nowrap;
}
.filter-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.city-input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.city-input {
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
.city-input:focus {
  border-color: var(--accent);
}
.city-icon {
  color: var(--secondary);
  font-size: 16px;
}
.ingredients-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--body);
  background: var(--bg);
  outline: none;
  font-family: var(--font-body);
  transition: border-color 0.2s;
}
.ingredients-input:focus {
  border-color: var(--accent);
}
.ingredients-hint {
  font-size: 12px;
  color: var(--secondary);
  margin-top: 6px;
}

@media (max-width: 640px) {
  .filter-two-col {
    grid-template-columns: 1fr;
  }
}
</style>
