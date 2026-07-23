import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { GenerateRequest, RecommendFilters, RecommendItem, ParsedIntent } from '../api/client'

/** 已识别标签项 */
export interface RecognizedTag {
  category: string  // 心情 / 食材 / 口味 / 辣度 / 菜系 / 烹饪时间 / 油盐偏好 / 忌口 / 健康目标
  value: string     // 显示文本
  field: string     // 对应 form/filters 的字段名
  source: 'form' | 'filters'  // 来自 form 还是 filters
}

export const useSessionStore = defineStore('session', () => {
  // ===== SSE 生成相关（保留原有） =====
  const sessionId = ref('')
  const recipeContent = ref('')
  const sources = ref<import('../api/client').RecipeSource[]>([])
  const isGenerating = ref(false)

  // ===== V4.0 对话+推荐相关 =====
  const lastIntentText = ref('')           // 用户最近一次输入的原文
  const queryText = ref('')                // parse_intent 返回的检索短句
  const filters = ref<RecommendFilters>({}) // 硬过滤条件
  const filterForm = ref<Partial<GenerateRequest>>({
    mood: '',
    taste: [],
    spice_level: 0,
    servings: 2,
    cook_time: '30分钟内',
    health_goal: '无',
    ingredients: [],
    city: '苏州',
    free_text: '',
  })
  const recommendations = ref<RecommendItem[]>([])
  const recommendMessage = ref('')         // 推荐结果的提示消息
  const recognizedTags = ref<RecognizedTag[]>([])
  const loading = ref(false)               // 推荐/解析中
  const excludedIds = ref<string[]>([])    // "换一个"时排除的菜 ID

  // ===== 我的食谱（本地收藏） =====
  const MY_RECIPES_KEY = 'shike_my_recipes'
  const myRecipes = ref<RecommendItem[]>(loadMyRecipes())

  function loadMyRecipes(): RecommendItem[] {
    try {
      const raw = localStorage.getItem(MY_RECIPES_KEY)
      if (!raw) return []
      const data = JSON.parse(raw)
      return Array.isArray(data) ? data : []
    } catch {
      return []
    }
  }

  function persistMyRecipes() {
    localStorage.setItem(MY_RECIPES_KEY, JSON.stringify(myRecipes.value))
  }

  const hasMyRecipes = computed(() => myRecipes.value.length > 0)

  function isInMyRecipes(id: string): boolean {
    return myRecipes.value.some(r => r.id === id)
  }

  /** 添加到我的食谱（按 id 去重） */
  function addToMyRecipes(item: RecommendItem): boolean {
    if (!item?.id) return false
    if (isInMyRecipes(item.id)) return false
    myRecipes.value = [item, ...myRecipes.value]
    persistMyRecipes()
    return true
  }

  /** 从我的食谱移除 */
  function removeFromMyRecipes(id: string) {
    myRecipes.value = myRecipes.value.filter(r => r.id !== id)
    persistMyRecipes()
  }

  /** 清空我的食谱 */
  function clearMyRecipes() {
    myRecipes.value = []
    persistMyRecipes()
  }

  // ===== computed =====
  const hasResults = computed(() => recommendations.value.length > 0)

  // ===== Actions =====

  function reset() {
    sessionId.value = ''
    recipeContent.value = ''
    sources.value = []
    isGenerating.value = false
  }

  function setSession(id: string) {
    sessionId.value = id
  }

  function appendContent(chunk: string) {
    recipeContent.value += chunk
  }

  function setSources(s: import('../api/client').RecipeSource[]) {
    sources.value = s
  }

  function setFormData(data: Partial<GenerateRequest>) {
    filterForm.value = { ...filterForm.value, ...data }
  }

  /** 从 parse_intent 结果更新全部状态 */
  function applyParsedIntent(parsed: ParsedIntent) {
    queryText.value = parsed.query_text
    filters.value = { ...parsed.filters }
    if (parsed.form) {
      filterForm.value = {
        mood: '',
        taste: [],
        spice_level: 0,
        servings: 2,
        cook_time: '30分钟内',
        health_goal: '无',
        ingredients: [],
        city: filterForm.value.city || '苏州',
        free_text: '',
        ...parsed.form,
      }
    }
    excludedIds.value = []
    rebuildRecognizedTags()
  }

  /** 根据 form + filters 重建已识别标签列表 */
  function rebuildRecognizedTags() {
    const tags: RecognizedTag[] = []
    const f = filterForm.value
    const fl = filters.value

    if (f.mood) tags.push({ category: '心情', value: f.mood, field: 'mood', source: 'form' })
    if (f.taste && f.taste.length) tags.push({ category: '口味', value: f.taste.join('、'), field: 'taste', source: 'form' })
    if (f.ingredients && f.ingredients.length) tags.push({ category: '食材', value: f.ingredients.join('、'), field: 'ingredients', source: 'form' })
    if (f.spice_level !== undefined && f.spice_level >= 0) {
      const labels = ['🌱不辣', '🌶️微辣', '🔥中辣', '💀重辣']
      tags.push({ category: '辣度', value: labels[f.spice_level] || '', field: 'spice_level', source: 'form' })
    }
    if (f.health_goal && f.health_goal !== '无') tags.push({ category: '健康目标', value: f.health_goal, field: 'health_goal', source: 'form' })
    if (fl.cuisine_main) tags.push({ category: '菜系', value: fl.cuisine_main, field: 'cuisine_main', source: 'filters' })
    if (fl.estimated_time_max) tags.push({ category: '烹饪时间', value: `${fl.estimated_time_max}min内`, field: 'estimated_time_max', source: 'filters' })
    if (fl.greasiness_max) {
      const g = fl.greasiness_max <= 2 ? '🧊清淡' : fl.greasiness_max <= 3 ? '⚖️适中' : '🫕浓郁'
      tags.push({ category: '油盐偏好', value: g, field: 'greasiness_max', source: 'filters' })
    }
    if (fl.exclude_allergens && fl.exclude_allergens.length) {
      tags.push({ category: '忌口', value: fl.exclude_allergens.join('、'), field: 'exclude_allergens', source: 'filters' })
    }

    recognizedTags.value = tags
  }

  /** 移除一个已识别标签，同时清除对应的 form/filters 字段 */
  function removeTag(tag: RecognizedTag) {
    if (tag.source === 'form') {
      if (tag.field === 'taste' || tag.field === 'ingredients') {
        ;(filterForm.value as Record<string, unknown>)[tag.field] = []
      } else {
        ;(filterForm.value as Record<string, unknown>)[tag.field] = tag.field === 'spice_level' ? 0 : ''
      }
    } else {
      ;(filters.value as Record<string, unknown>)[tag.field] = tag.field === 'exclude_allergens' ? [] : null
    }
    rebuildRecognizedTags()
  }

  /** 设置推荐结果 */
  function setRecommendations(items: RecommendItem[], message = '') {
    recommendations.value = items
    recommendMessage.value = message
  }

  /** 排除某个菜 ID（"换一个"用） */
  function addExcludedId(id: string) {
    if (!excludedIds.value.includes(id)) {
      excludedIds.value.push(id)
    }
  }

  /** 更新 filters（手动筛选面板修改后） */
  function updateFilters(newFilters: RecommendFilters) {
    filters.value = { ...newFilters }
    rebuildRecognizedTags()
  }

  /** 更新 form（手动筛选面板修改后） */
  function updateForm(newForm: Partial<GenerateRequest>) {
    filterForm.value = { ...filterForm.value, ...newForm }
    rebuildRecognizedTags()
  }

  return {
    // SSE
    sessionId,
    recipeContent,
    sources,
    isGenerating,
    // V4.0
    lastIntentText,
    queryText,
    filters,
    filterForm,
    recommendations,
    recommendMessage,
    recognizedTags,
    loading,
    excludedIds,
    hasResults,
    myRecipes,
    hasMyRecipes,
    // actions
    reset,
    setSession,
    appendContent,
    setSources,
    setFormData,
    applyParsedIntent,
    rebuildRecognizedTags,
    removeTag,
    setRecommendations,
    addExcludedId,
    updateFilters,
    updateForm,
    isInMyRecipes,
    addToMyRecipes,
    removeFromMyRecipes,
    clearMyRecipes,
  }
})
