/**
 * LoginView 组件测试：空表单校验与登录成功跳转。
 */
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import LoginView from '@/views/LoginView.vue'

const loginMock = vi.fn()

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: loginMock,
    loading: false,
  }),
}))

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    loginMock.mockReset()
  })

  async function mountLogin(query: Record<string, string> = {}) {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: LoginView },
        { path: '/', component: { template: '<div>home</div>' } },
        { path: '/favorites', component: { template: '<div>fav</div>' } },
        { path: '/register', component: { template: '<div>reg</div>' } },
      ],
    })
    await router.push({ path: '/login', query })
    await router.isReady()
    return mount(LoginView, {
      global: {
        plugins: [router],
      },
    })
  }

  it('空提交时提示输入用户名和密码', async () => {
    const wrapper = await mountLogin()
    await wrapper.get('[data-testid="login-submit"]').trigger('submit')
    // form @submit.prevent 绑定在 form 上
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[data-testid="login-error"]').text()).toContain('请输入用户名和密码')
    expect(loginMock).not.toHaveBeenCalled()
  })

  it('登录成功后跳转到 redirect', async () => {
    loginMock.mockResolvedValue({})
    const wrapper = await mountLogin({ redirect: '/favorites' })
    await wrapper.get('[data-testid="login-username"]').setValue('leo')
    await wrapper.get('[data-testid="login-password"]').setValue('secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(loginMock).toHaveBeenCalledWith('leo', 'secret')
    expect(wrapper.vm.$router.currentRoute.value.fullPath).toBe('/favorites')
  })
})
