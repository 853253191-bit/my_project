/** 请求工具：带鉴权的 fetch、防抖、并行加载。 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const ACCESS_KEY = 'shike_access_token'
const REFRESH_KEY = 'shike_refresh_token'

export function getAccessToken(): string {
  return localStorage.getItem(ACCESS_KEY) || ''
}

export function getRefreshToken(): string {
  return localStorage.getItem(REFRESH_KEY) || ''
}

export function setTokens(access: string, refresh?: string) {
  localStorage.setItem(ACCESS_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export type ApiFetchOptions = RequestInit & {
  auth?: boolean
  json?: unknown
}

/** 带 JSON / Authorization 的请求封装；401 时尝试 refresh 一次 */
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  if (options.auth !== false) {
    const token = getAccessToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }

  const doRequest = async () =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
    })

  let resp = await doRequest()
  if (resp.status === 401 && options.auth !== false) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      const token = getAccessToken()
      if (token) headers.set('Authorization', `Bearer ${token}`)
      resp = await doRequest()
    }
  }
  if (!resp.ok) {
    let detail = `请求失败: ${resp.status}`
    try {
      const data = await resp.json()
      detail = data.detail || data.message || detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  try {
    const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!resp.ok) {
      clearTokens()
      return false
    }
    const data = await resp.json()
    if (data.access_token) {
      setTokens(data.access_token)
      return true
    }
  } catch {
    clearTokens()
  }
  return false
}

/** 防抖 */
export function debounce<T extends (...args: never[]) => void>(fn: T, wait = 500): T {
  let timer: ReturnType<typeof setTimeout> | null = null
  return ((...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), wait)
  }) as T
}

/** 首页并行请求示例 */
export async function loadHomeParallel(city?: string) {
  const tasks: Promise<unknown>[] = [
    apiFetch('/api/daily_recommendations?limit=5', { auth: false }),
  ]
  if (city) {
    tasks.push(
      apiFetch(`/api/weather?city=${encodeURIComponent(city)}`, { auth: false }),
    )
  }
  return Promise.all(tasks)
}
