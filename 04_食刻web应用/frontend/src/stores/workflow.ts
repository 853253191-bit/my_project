import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** 推荐主流程阶段 */
export type WorkflowPhase =
  | 'idle'
  | 'parsing'
  | 'recommending'
  | 'results'
  | 'empty'
  | 'detail_loading'
  | 'generating'
  | 'detail_ready'
  | 'error'

/** 驱动流转的事件 */
export type WorkflowEvent =
  | 'SEND'
  | 'PARSE_OK'
  | 'RECOMMEND_OK'
  | 'RECOMMEND_EMPTY'
  | 'SPARK'
  | 'CHANGE_ONE'
  | 'OPEN_DETAIL'
  | 'DETAIL_OK'
  | 'GENERATE'
  | 'GENERATE_OK'
  | 'FAIL'
  | 'CLOSE_DETAIL'
  | 'RESET'

export interface WorkflowHistoryItem {
  id: number
  at: number
  event: WorkflowEvent
  from: WorkflowPhase
  to: WorkflowPhase
  note?: string
}

/** 阶段中文标签（流转条展示） */
export const PHASE_LABELS: Record<WorkflowPhase, string> = {
  idle: '待命',
  parsing: '解析意图',
  recommending: '检索推荐',
  results: '有推荐',
  empty: '无结果',
  detail_loading: '加载详情',
  generating: '生成做法',
  detail_ready: '详情就绪',
  error: '出错',
}

/** 主路径步骤（用于顶部进度条，不含 error） */
export const MAIN_STEPS: WorkflowPhase[] = [
  'idle',
  'parsing',
  'recommending',
  'results',
  'detail_loading',
  'generating',
  'detail_ready',
]

/** 合法转移表：from + event -> to */
const TRANSITIONS: Record<WorkflowPhase, Partial<Record<WorkflowEvent, WorkflowPhase>>> = {
  idle: {
    SEND: 'parsing',
    SPARK: 'recommending',
    OPEN_DETAIL: 'detail_loading',
    RESET: 'idle',
  },
  parsing: {
    PARSE_OK: 'recommending',
    OPEN_DETAIL: 'detail_loading',
    FAIL: 'error',
    RESET: 'idle',
  },
  recommending: {
    RECOMMEND_OK: 'results',
    RECOMMEND_EMPTY: 'empty',
    OPEN_DETAIL: 'detail_loading',
    FAIL: 'error',
    RESET: 'idle',
  },
  results: {
    SEND: 'parsing',
    SPARK: 'recommending',
    CHANGE_ONE: 'recommending',
    OPEN_DETAIL: 'detail_loading',
    RESET: 'idle',
  },
  empty: {
    SEND: 'parsing',
    SPARK: 'recommending',
    CHANGE_ONE: 'recommending',
    OPEN_DETAIL: 'detail_loading',
    RESET: 'idle',
  },
  detail_loading: {
    DETAIL_OK: 'detail_ready',
    GENERATE: 'generating',
    FAIL: 'error',
    CLOSE_DETAIL: 'results',
    RESET: 'idle',
  },
  generating: {
    GENERATE_OK: 'detail_ready',
    FAIL: 'error',
    CLOSE_DETAIL: 'results',
    RESET: 'idle',
  },
  detail_ready: {
    CLOSE_DETAIL: 'results',
    OPEN_DETAIL: 'detail_loading',
    SEND: 'parsing',
    SPARK: 'recommending',
    RESET: 'idle',
  },
  error: {
    SEND: 'parsing',
    SPARK: 'recommending',
    CHANGE_ONE: 'recommending',
    OPEN_DETAIL: 'detail_loading',
    CLOSE_DETAIL: 'results',
    RESET: 'idle',
  },
}

const HISTORY_LIMIT = 30

export const useWorkflowStore = defineStore('workflow', () => {
  const phase = ref<WorkflowPhase>('idle')
  const lastError = ref('')
  const history = ref<WorkflowHistoryItem[]>([])
  /** 打开详情前的列表态，关闭详情时回到此处 */
  const returnPhase = ref<WorkflowPhase>('idle')
  let seq = 0

  const phaseLabel = computed(() => PHASE_LABELS[phase.value])
  const isBusy = computed(() =>
    ['parsing', 'recommending', 'detail_loading', 'generating'].includes(phase.value),
  )

  function pushHistory(
    event: WorkflowEvent,
    from: WorkflowPhase,
    to: WorkflowPhase,
    note?: string,
  ) {
    seq += 1
    history.value = [
      { id: seq, at: Date.now(), event, from, to, note },
      ...history.value,
    ].slice(0, HISTORY_LIMIT)
  }

  /**
   * 尝试按转移表跳转；非法跳转仅告警并返回 false，不改变 phase。
   */
  function send(event: WorkflowEvent, note?: string): boolean {
    const from = phase.value
    let to = TRANSITIONS[from]?.[event]

    if (!to) {
      console.warn(`[workflow] 非法跳转: ${from} + ${event}`)
      return false
    }

    // 关闭详情：回到打开前的列表态
    if (event === 'CLOSE_DETAIL') {
      to = ['results', 'empty', 'idle'].includes(returnPhase.value)
        ? returnPhase.value
        : 'results'
    }

    // 进入详情前记住列表态
    if (event === 'OPEN_DETAIL' && ['idle', 'results', 'empty'].includes(from)) {
      returnPhase.value = from
    }

    if (event === 'FAIL' && note) {
      lastError.value = note
    } else if (event !== 'FAIL') {
      lastError.value = ''
    }

    if (event === 'RESET') {
      returnPhase.value = 'idle'
      lastError.value = ''
    }

    phase.value = to
    pushHistory(event, from, to, note)
    return true
  }

  /** 开发调试：强制设阶段（不计入正常转移校验） */
  function force(to: WorkflowPhase, note = 'force') {
    const from = phase.value
    phase.value = to
    pushHistory('RESET', from, to, note)
  }

  function clearHistory() {
    history.value = []
  }

  return {
    phase,
    phaseLabel,
    lastError,
    history,
    returnPhase,
    isBusy,
    send,
    force,
    clearHistory,
  }
})
