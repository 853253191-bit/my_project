const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

// ===== Types =====

export interface GenerateRequest {
  mood: string
  taste: string[]
  spice_level: number
  servings: number
  cook_time: string
  health_goal: string
  ingredients: string[]
  city: string
  free_text: string
}

export interface RecipeSource {
  id: string
  title: string
  source_url: string
}

export interface WeatherInfo {
  city: string
  weather: string
  temperature: string
  report_time: string
}

/** /api/recommend 硬过滤条件 */
export interface RecommendFilters {
  greasiness_max?: number | null
  spicy_level_max?: number | null
  cuisine_main?: string | null
  ai_difficulty?: string | null
  estimated_time_max?: number | null
  exclude_allergens?: string[]
  include_diet_labels?: string[]
}

/** /api/recommend 请求 */
export interface RecommendRequest {
  query_text: string
  filters: RecommendFilters
  top_k?: number
}

/** /api/recommend 或 /api/random 返回的菜品 item */
export interface RecommendItem {
  id: string
  title: string
  decision_summary: string
  /** 动态推荐理由（优先展示） */
  reason?: string
  cuisine_main?: string
  greasiness?: number
  spicy_level?: number
  ai_difficulty?: string
  estimated_time?: number
  allergens_str?: string
  diet_labels_str?: string
  ai_tags?: Record<string, unknown> | null
  image_url?: string
  source_url?: string
  distance?: number
  ingredients?: string[]
  is_favorited?: boolean
}

/** /api/recommend 响应 */
export interface RecommendResponse {
  count: number
  message: string
  items: RecommendItem[]
  /** 1=严格 2=放宽 3=随机兜底 */
  recall_level?: number
}

/** /api/parse_intent 响应 */
export interface ParsedIntent {
  query_text: string
  filters: RecommendFilters
  form: {
    mood?: string
    taste?: string[]
    spice_level?: number
    servings?: number
    cook_time?: string
    health_goal?: string
    ingredients?: string[]
    free_text?: string
  }
}

/** /api/daily_recommendations item */
export interface DailyItem {
  id: string
  title: string
  decision_summary: string
  cuisine_main?: string
  estimated_time?: number
  ai_difficulty?: string
  image_url?: string
  ingredients?: string[]
}

// ===== SSE streaming =====

export async function* streamSSE(
  url: string,
  body: unknown,
): AsyncGenerator<{ event: string; data: Record<string, unknown> }> {
  const resp = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`请求失败: ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      if (!part.trim()) continue
      let event = 'message'
      let dataStr = ''
      for (const line of part.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7)
        if (line.startsWith('data: ')) dataStr = line.slice(6)
      }
      if (dataStr) {
        yield { event, data: JSON.parse(dataStr) }
      }
    }
  }
}

// ===== API functions =====

/** SSE: 生成完整食谱 */
export function generateRecipe(req: GenerateRequest) {
  return streamSSE('/api/recipes/generate', req)
}

/** SSE: 对话微调（需 session_id） */
export function chatRecipe(sessionId: string, message: string) {
  return streamSSE('/api/chat', { session_id: sessionId, message })
}

/** 意图解析：自然语言 -> 结构化 filters + form */
export async function parseIntent(text: string): Promise<ParsedIntent> {
  const resp = await fetch(`${API_BASE}/api/parse_intent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!resp.ok) throw new Error(`意图解析失败: ${resp.status}`)
  return resp.json()
}

/** 混合检索推荐：query_text 走向量，filters 走硬过滤 */
export async function recommend(
  queryText: string,
  filters: RecommendFilters,
  topK = 5,
): Promise<RecommendResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  try {
    const { getAccessToken } = await import('../utils/request')
    const token = getAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  } catch {
    /* ignore */
  }
  const resp = await fetch(`${API_BASE}/api/recommend`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query_text: queryText, filters, top_k: topK }),
  })
  if (!resp.ok) throw new Error(`推荐失败: ${resp.status}`)
  return resp.json()
}

/** 提交推荐反馈（好评 / 差评） */
export async function submitFeedback(payload: {
  recipe_id: string
  rating: 'good' | 'bad' | 'skip'
  session_id?: string
  user_id?: string
  query_text?: string
  filters?: RecommendFilters
  comment?: string
}): Promise<{ ok: boolean; id: number; message: string }> {
  const resp = await fetch(`${API_BASE}/api/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) throw new Error(`反馈提交失败: ${resp.status}`)
  return resp.json()
}

/** 随机菜谱 */
export async function getRandom(): Promise<RecommendItem> {
  const resp = await fetch(`${API_BASE}/api/random`)
  if (!resp.ok) throw new Error(`随机推荐失败: ${resp.status}`)
  return resp.json()
}

/** 每日推荐 */
export async function getDailyRecommendations(limit = 5): Promise<{ count: number; items: DailyItem[] }> {
  const resp = await fetch(`${API_BASE}/api/daily_recommendations?limit=${limit}`)
  if (!resp.ok) throw new Error(`每日推荐失败: ${resp.status}`)
  return resp.json()
}

/** 天气查询 */
export async function fetchWeather(city: string): Promise<WeatherInfo> {
  const resp = await fetch(`${API_BASE}/api/weather?city=${encodeURIComponent(city)}`)
  if (!resp.ok) throw new Error('天气查询失败')
  return resp.json()
}

/** 获取会话详情 */
export async function fetchSession(sessionId: string) {
  const resp = await fetch(`${API_BASE}/api/sessions/${sessionId}`)
  if (!resp.ok) throw new Error('会话不存在')
  return resp.json()
}

// ===== Helpers =====

/** 后端 spicy_level (0-5) -> 前端显示标签 */
export function spicyLabel(level: number | undefined): string {
  if (level === undefined || level === 0) return '不辣'
  if (level <= 2) return '微辣'
  if (level <= 4) return '中辣'
  return '重辣'
}

/** 后端 estimated_time (分钟) -> 显示文本 */
export function timeLabel(minutes: number | undefined): string {
  if (!minutes || minutes === 0) return '不限'
  if (minutes < 60) return `${minutes}min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h}h${m}min` : `${h}h`
}

/** 后端 greasiness (1-5) -> 显示文本 */
export function greasinessLabel(level: number | undefined): string {
  if (!level) return ''
  if (level <= 2) return '清淡'
  if (level <= 3) return '适中'
  return '浓郁'
}

/** 后端 ai_difficulty -> 中文 */
export function difficultyLabel(d: string | undefined): string {
  if (!d) return ''
  const map: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
  return map[d] || d
}
