/**
 * auth Store 单元测试
 * 重点：登录态 computed、logout 清 token、login/fetchMe 调用 mock API。
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/utils/request', () => ({
  apiFetch: vi.fn(),
  getAccessToken: vi.fn(() => ''),
  getRefreshToken: vi.fn(() => ''),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
}))

import { useAuthStore } from '@/stores/auth'
import * as request from '@/utils/request'

const apiFetch = vi.mocked(request.apiFetch)
const getAccessToken = vi.mocked(request.getAccessToken)
const setTokens = vi.mocked(request.setTokens)
const clearTokens = vi.mocked(request.clearTokens)

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getAccessToken.mockReturnValue('')
  })

  it('未登录时 isLoggedIn 为 false，头像字母为「客」', () => {
    const auth = useAuthStore()
    expect(auth.isLoggedIn).toBe(false)
    expect(auth.avatarLetter).toBe('客')
  })

  it('login 成功后写入 token 并拉取用户信息', async () => {
    apiFetch
      .mockResolvedValueOnce({
        access_token: 'acc',
        refresh_token: 'ref',
        token_type: 'bearer',
      })
      .mockResolvedValueOnce({
        id: 1,
        username: 'leo',
        email: 'leo@example.com',
        preferences: {},
      })

    getAccessToken.mockReturnValue('acc')

    const auth = useAuthStore()
    await auth.login('leo', 'secret')

    expect(setTokens).toHaveBeenCalledWith('acc', 'ref')
    expect(auth.user?.username).toBe('leo')
    expect(auth.isLoggedIn).toBe(true)
    expect(auth.displayName).toBe('leo')
    expect(auth.avatarLetter).toBe('L')
    expect(auth.loading).toBe(false)
  })

  it('logout 清空用户与 token', () => {
    const auth = useAuthStore()
    auth.user = {
      id: 1,
      username: 'leo',
      email: 'a@b.c',
      preferences: {},
    }
    auth.accessToken = 'acc'
    auth.logout()
    expect(clearTokens).toHaveBeenCalled()
    expect(auth.user).toBeNull()
    expect(auth.accessToken).toBe('')
    expect(auth.isLoggedIn).toBe(false)
  })

  it('fetchMe 无 token 时直接返回 null', async () => {
    getAccessToken.mockReturnValue('')
    const auth = useAuthStore()
    const me = await auth.fetchMe()
    expect(me).toBeNull()
    expect(apiFetch).not.toHaveBeenCalled()
  })
})
