<script setup lang="ts">
import { ref } from 'vue'
import { apiFetch } from '../utils/request'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const categories = ['建议', '问题', '表扬', '其他'] as const
const category = ref<(typeof categories)[number]>('建议')
const content = ref('')
const contact = ref('')
const submitting = ref(false)
const done = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  done.value = false
  const text = content.value.trim()
  if (text.length < 5) {
    error.value = '请至少写 5 个字哦'
    return
  }
  submitting.value = true
  try {
    await apiFetch('/api/site-feedback', {
      method: 'POST',
      json: {
        content: text,
        contact: contact.value.trim() || undefined,
        category: category.value,
      },
      auth: auth.isLoggedIn,
    })
    done.value = true
    content.value = ''
    contact.value = ''
    category.value = '建议'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提交失败，请稍后再试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="card">
      <h1>意见反馈</h1>
      <p class="lead">
        使用中有不爽、想加的功能，或夸我们一句，都欢迎写下来。我们会定期整理并改进。
      </p>

      <div v-if="done" class="ok">感谢反馈！我们已收到，会认真阅读～</div>

      <label class="field-label">反馈类型</label>
      <div class="cats">
        <button
          v-for="c in categories"
          :key="c"
          type="button"
          class="cat"
          :class="{ on: category === c }"
          @click="category = c"
        >
          {{ c }}
        </button>
      </div>

      <label class="field-label" for="fb-content">你的意见</label>
      <textarea
        id="fb-content"
        v-model="content"
        class="ta"
        rows="6"
        maxlength="2000"
        placeholder="随便说，例如：希望能按预算推荐、详情页字体再大一点…"
      />
      <div class="count">{{ content.trim().length }} / 2000</div>

      <label class="field-label" for="fb-contact">联系方式（选填）</label>
      <input
        id="fb-contact"
        v-model="contact"
        class="inp"
        type="text"
        maxlength="120"
        placeholder="邮箱 / 微信，方便我们必要时回访"
      />

      <p v-if="auth.isLoggedIn" class="hint">
        当前已登录：{{ auth.displayName }}，提交时会一并记录账号信息。
      </p>
      <p v-else class="hint">未登录也可匿名提交。</p>

      <p v-if="error" class="err">{{ error }}</p>

      <button
        type="button"
        class="btn btn-primary submit"
        :disabled="submitting"
        @click="submit"
      >
        {{ submitting ? '提交中…' : '提交反馈' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 640px;
  margin: 0 auto;
}
.card {
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: 28px 28px 32px;
}
h1 {
  font-family: var(--font-title);
  font-size: 28px;
  font-weight: 600;
  color: var(--title);
  margin-bottom: 8px;
}
.lead {
  font-size: 14px;
  color: var(--secondary);
  line-height: 1.7;
  margin-bottom: 22px;
}
.ok {
  margin-bottom: 16px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: #eef9f0;
  color: #2d7a3e;
  font-size: 14px;
}
.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--title);
  margin: 14px 0 8px;
}
.cats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cat {
  padding: 6px 14px;
  border: 1px solid var(--divider);
  border-radius: 999px;
  background: #fff;
  color: var(--body);
  font-size: 13px;
  font-family: var(--font-body);
  cursor: pointer;
  transition: all 0.15s;
}
.cat.on {
  background: #fff0e0;
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}
.ta,
.inp {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-family: var(--font-body);
  color: var(--body);
  background: var(--bg);
  outline: none;
}
.ta:focus,
.inp:focus {
  border-color: var(--accent);
}
.ta {
  resize: vertical;
  min-height: 120px;
  line-height: 1.6;
}
.count {
  text-align: right;
  font-size: 12px;
  color: var(--secondary);
  margin-top: 4px;
}
.hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--secondary);
}
.err {
  margin-top: 10px;
  color: #c0392b;
  font-size: 13px;
}
.submit {
  margin-top: 18px;
  width: 100%;
}
</style>
