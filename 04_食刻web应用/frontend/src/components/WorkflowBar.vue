<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  MAIN_STEPS,
  PHASE_LABELS,
  useWorkflowStore,
  type WorkflowPhase,
} from '../stores/workflow'

const workflow = useWorkflowStore()
const expanded = ref(true)

/** 当前阶段在主路径上的索引；empty/error 单独处理 */
const activeStepIndex = computed(() => {
  const p = workflow.phase
  if (p === 'empty') return MAIN_STEPS.indexOf('results')
  if (p === 'error') return -1
  return MAIN_STEPS.indexOf(p)
})

function stepClass(step: WorkflowPhase, index: number) {
  const active = activeStepIndex.value
  const current = workflow.phase
  const isCurrent =
    current === step ||
    (current === 'empty' && step === 'results')
  return {
    'is-current': isCurrent,
    'is-done': active > index && !isCurrent,
    'is-error': current === 'error',
    'is-empty-alt': current === 'empty' && step === 'results',
  }
}

function stepLabel(step: WorkflowPhase) {
  if (workflow.phase === 'empty' && step === 'results') return PHASE_LABELS.empty
  return PHASE_LABELS[step]
}

function formatTime(ts: number) {
  const d = new Date(ts)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}
</script>

<template>
  <div class="workflow-bar" data-testid="workflow-bar" :class="{ collapsed: !expanded }">
    <div class="wb-header">
      <div class="wb-title-row">
        <span class="wb-badge">状态机</span>
        <span class="wb-current" data-testid="workflow-current">
          当前：<strong data-testid="workflow-phase-label">{{ workflow.phaseLabel }}</strong>
          <code class="wb-phase-code" data-testid="workflow-phase">{{ workflow.phase }}</code>
        </span>
        <span v-if="workflow.lastError" class="wb-error" :title="workflow.lastError">
          {{ workflow.lastError }}
        </span>
      </div>
      <div class="wb-actions">
        <button
          type="button"
          class="wb-btn"
          data-testid="workflow-clear"
          @click="workflow.clearHistory()"
        >
          清空记录
        </button>
        <button
          type="button"
          class="wb-btn"
          data-testid="workflow-toggle"
          @click="expanded = !expanded"
        >
          {{ expanded ? '收起' : '展开' }}
        </button>
      </div>
    </div>

    <ol class="wb-steps" aria-label="主流程阶段">
      <li
        v-for="(step, index) in MAIN_STEPS"
        :key="step"
        class="wb-step"
        :class="stepClass(step, index)"
      >
        <span class="wb-dot" />
        <span class="wb-step-label">{{ stepLabel(step) }}</span>
        <span v-if="index < MAIN_STEPS.length - 1" class="wb-connector" aria-hidden="true" />
      </li>
    </ol>

    <div v-if="expanded" class="wb-history">
      <div class="wb-history-title">最近流转</div>
      <ul v-if="workflow.history.length" class="wb-history-list">
        <li v-for="item in workflow.history" :key="item.id" class="wb-history-item">
          <span class="wb-time">{{ formatTime(item.at) }}</span>
          <span class="wb-from">{{ PHASE_LABELS[item.from] }}</span>
          <span class="wb-arrow">-{{ item.event }}-&gt;</span>
          <span class="wb-to">{{ PHASE_LABELS[item.to] }}</span>
          <span v-if="item.note" class="wb-note">{{ item.note }}</span>
        </li>
      </ul>
      <div v-else class="wb-history-empty">尚无流转记录，发送一句需求后会出现在这里</div>
    </div>
  </div>
</template>

<style scoped>
.workflow-bar {
  background: var(--card);
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  padding: 14px 16px 12px;
  margin-bottom: 28px;
  box-shadow: var(--shadow);
}

.wb-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.wb-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.wb-badge {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--accent-dark);
  background: var(--accent-light);
  padding: 3px 8px;
  border-radius: 6px;
}

.wb-current {
  font-size: 13px;
  color: var(--body);
}

.wb-current strong {
  color: var(--title);
}

.wb-phase-code {
  margin-left: 6px;
  font-size: 11px;
  color: var(--secondary);
  background: #f5efe6;
  padding: 2px 6px;
  border-radius: 4px;
}

.wb-error {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #b33a2b;
}

.wb-actions {
  display: flex;
  gap: 8px;
}

.wb-btn {
  border: 1px solid var(--divider);
  background: #fff;
  color: var(--body);
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.wb-btn:hover {
  border-color: var(--accent);
  color: var(--accent-dark);
}

.wb-steps {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0;
  margin: 0;
  padding: 0 0 4px;
}

.wb-step {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1 1 72px;
  min-width: 64px;
  max-width: 110px;
  gap: 6px;
}

.wb-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #e8ddd0;
  border: 2px solid #d9cbb8;
  z-index: 1;
  transition: background 0.2s, border-color 0.2s, transform 0.2s;
}

.wb-step-label {
  font-size: 11px;
  color: var(--secondary);
  text-align: center;
  line-height: 1.3;
}

.wb-connector {
  position: absolute;
  top: 5px;
  left: calc(50% + 10px);
  width: calc(100% - 20px);
  height: 2px;
  background: #e8ddd0;
  z-index: 0;
}

.wb-step.is-done .wb-dot {
  background: var(--accent);
  border-color: var(--accent-dark);
}

.wb-step.is-done .wb-connector {
  background: #f0c49a;
}

.wb-step.is-current .wb-dot {
  background: var(--accent-dark);
  border-color: var(--accent-dark);
  transform: scale(1.25);
  box-shadow: 0 0 0 4px rgba(230, 126, 34, 0.18);
}

.wb-step.is-current .wb-step-label {
  color: var(--title);
  font-weight: 700;
}

.wb-step.is-empty-alt .wb-dot {
  background: #c4a574;
  border-color: #a88858;
}

.wb-step.is-error .wb-dot {
  background: #d96b5c;
  border-color: #b33a2b;
}

.wb-history {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--divider);
}

.wb-history-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--title);
  margin-bottom: 8px;
}

.wb-history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 140px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wb-history-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 8px;
  font-size: 12px;
  color: var(--body);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.wb-time {
  color: var(--secondary);
  min-width: 64px;
}

.wb-from,
.wb-to {
  color: var(--title);
}

.wb-arrow {
  color: var(--accent-dark);
  font-size: 11px;
}

.wb-note {
  color: var(--secondary);
  font-family: var(--font-body);
}

.wb-history-empty {
  font-size: 12px;
  color: var(--secondary);
}

.workflow-bar.collapsed .wb-steps {
  margin-bottom: 0;
}

@media (max-width: 640px) {
  .wb-step {
    flex: 1 1 48px;
    min-width: 48px;
  }
  .wb-step-label {
    font-size: 10px;
  }
}
</style>
