/**
 * FeedbackView 组件测试：字数校验与提交成功态。
 */
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FeedbackView from '@/views/FeedbackView.vue'

const apiFetch = vi.fn()

vi.mock('@/utils/request', () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isLoggedIn: false,
    displayName: '',
  }),
}))

describe('FeedbackView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    apiFetch.mockReset()
  })

  it('少于 5 字时显示错误，不发请求', async () => {
    const wrapper = mount(FeedbackView)
    await wrapper.get('[data-testid="feedback-content"]').setValue('短')
    await wrapper.get('[data-testid="feedback-submit"]').trigger('click')
    expect(wrapper.get('[data-testid="feedback-error"]').text()).toContain('至少写 5 个字')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('合法内容提交成功后展示成功提示', async () => {
    apiFetch.mockResolvedValue({ id: 1 })
    const wrapper = mount(FeedbackView)
    await wrapper.get('[data-testid="feedback-content"]').setValue('希望能按预算推荐菜谱')
    await wrapper.get('[data-testid="feedback-submit"]').trigger('click')
    await flushPromises()
    expect(apiFetch).toHaveBeenCalled()
    expect(wrapper.get('[data-testid="feedback-success"]').text()).toContain('感谢反馈')
  })
})
