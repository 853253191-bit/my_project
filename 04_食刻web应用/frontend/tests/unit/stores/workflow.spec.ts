/**
 * workflow Store 单元测试
 * 重点：合法/非法状态转移、关闭详情回退、忙碌态 computed。
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useWorkflowStore } from '@/stores/workflow'

describe('useWorkflowStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('初始阶段为 idle，且不忙碌', () => {
    const wf = useWorkflowStore()
    expect(wf.phase).toBe('idle')
    expect(wf.phaseLabel).toBe('待命')
    expect(wf.isBusy).toBe(false)
  })

  it('主路径：SEND → PARSE_OK → RECOMMEND_OK 到达 results', () => {
    const wf = useWorkflowStore()
    expect(wf.send('SEND')).toBe(true)
    expect(wf.phase).toBe('parsing')
    expect(wf.isBusy).toBe(true)

    expect(wf.send('PARSE_OK')).toBe(true)
    expect(wf.phase).toBe('recommending')

    expect(wf.send('RECOMMEND_OK')).toBe(true)
    expect(wf.phase).toBe('results')
    expect(wf.isBusy).toBe(false)
    expect(wf.history.length).toBeGreaterThanOrEqual(3)
  })

  it('非法跳转不改变阶段并返回 false', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const wf = useWorkflowStore()
    expect(wf.send('RECOMMEND_OK')).toBe(false)
    expect(wf.phase).toBe('idle')
    expect(warn).toHaveBeenCalled()
  })

  it('OPEN_DETAIL 记住列表态，CLOSE_DETAIL 回到 results', () => {
    const wf = useWorkflowStore()
    wf.send('SEND')
    wf.send('PARSE_OK')
    wf.send('RECOMMEND_OK')
    expect(wf.phase).toBe('results')

    wf.send('OPEN_DETAIL')
    expect(wf.phase).toBe('detail_loading')
    expect(wf.returnPhase).toBe('results')

    wf.send('DETAIL_OK')
    expect(wf.phase).toBe('detail_ready')

    wf.send('CLOSE_DETAIL')
    expect(wf.phase).toBe('results')
  })

  it('FAIL 记录错误信息，RESET 清空并回到 idle', () => {
    const wf = useWorkflowStore()
    wf.send('SEND')
    wf.send('FAIL', '网络超时')
    expect(wf.phase).toBe('error')
    expect(wf.lastError).toBe('网络超时')

    wf.send('RESET')
    expect(wf.phase).toBe('idle')
    expect(wf.lastError).toBe('')
    expect(wf.returnPhase).toBe('idle')
  })
})
