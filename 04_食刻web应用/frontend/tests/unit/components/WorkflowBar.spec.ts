/**
 * WorkflowBar 组件测试：展开收起与清空流转记录。
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import WorkflowBar from '@/components/WorkflowBar.vue'
import { useWorkflowStore } from '@/stores/workflow'

describe('WorkflowBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('展示当前阶段标签，并可收起/展开历史区', async () => {
    const wf = useWorkflowStore()
    wf.send('SEND')
    const wrapper = mount(WorkflowBar)
    expect(wrapper.get('[data-testid="workflow-phase"]').text()).toBe('parsing')
    expect(wrapper.get('[data-testid="workflow-phase-label"]').text()).toBe('解析意图')
    expect(wrapper.find('.wb-history').exists()).toBe(true)

    await wrapper.get('[data-testid="workflow-toggle"]').trigger('click')
    expect(wrapper.find('.wb-history').exists()).toBe(false)
    expect(wrapper.get('[data-testid="workflow-toggle"]').text()).toBe('展开')
  })

  it('清空记录会调用 clearHistory', async () => {
    const wf = useWorkflowStore()
    wf.send('SEND')
    expect(wf.history.length).toBeGreaterThan(0)
    const wrapper = mount(WorkflowBar)
    await wrapper.get('[data-testid="workflow-clear"]').trigger('click')
    expect(wf.history).toHaveLength(0)
  })
})
