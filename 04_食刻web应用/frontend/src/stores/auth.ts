import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  apiFetch,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from '../utils/request'

export interface AuthUser {
  id: number
  username: string
  email: string
  preferences: Record<string, unknown>
  is_active?: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(getAccessToken())
  const refreshToken = ref(getRefreshToken())
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!accessToken.value && !!user.value)
  const displayName = computed(() => user.value?.username || '')
  const avatarLetter = computed(() => {
    const n = displayName.value
    return n ? n.slice(0, 1).toUpperCase() : '客'
  })

  function persistTokens(access: string, refresh?: string) {
    setTokens(access, refresh)
    accessToken.value = access
    if (refresh) refreshToken.value = refresh
  }

  async function register(payload: {
    username: string
    email: string
    password: string
  }) {
    loading.value = true
    try {
      return await apiFetch<{ user_id: number; username: string }>(
        '/api/auth/register',
        { method: 'POST', json: payload, auth: false },
      )
    } finally {
      loading.value = false
    }
  }

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const data = await apiFetch<{
        access_token: string
        refresh_token: string
        token_type: string
      }>('/api/auth/login', {
        method: 'POST',
        json: { username, password },
        auth: false,
      })
      persistTokens(data.access_token, data.refresh_token)
      await fetchMe()
      return data
    } finally {
      loading.value = false
    }
  }

  async function fetchMe() {
    if (!getAccessToken()) {
      user.value = null
      return null
    }
    try {
      const me = await apiFetch<AuthUser>('/api/auth/me')
      user.value = me
      return me
    } catch {
      logout()
      return null
    }
  }

  async function updatePreferences(preferences: Record<string, unknown>) {
    const data = await apiFetch<{ id: number; preferences: Record<string, unknown> }>(
      '/api/auth/me',
      { method: 'PUT', json: { preferences } },
    )
    if (user.value) {
      user.value = { ...user.value, preferences: data.preferences }
    }
    return data
  }

  function logout() {
    clearTokens()
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
  }

  /** 应用启动时恢复会话 */
  async function bootstrap() {
    if (!getAccessToken()) return
    await fetchMe()
  }

  return {
    accessToken,
    user,
    loading,
    isLoggedIn,
    displayName,
    avatarLetter,
    register,
    login,
    fetchMe,
    updatePreferences,
    logout,
    bootstrap,
  }
})
