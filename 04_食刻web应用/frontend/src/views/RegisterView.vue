<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function onSubmit() {
  error.value = ''
  if (!username.value.trim() || !email.value.trim() || password.value.length < 6) {
    error.value = '请填写完整信息，密码至少 6 位'
    return
  }
  submitting.value = true
  try {
    await auth.register({
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value,
    })
    await auth.login(username.value.trim(), password.value)
    router.replace('/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '注册失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-page" data-testid="register-page">
    <h1 class="auth-title">注册食刻</h1>
    <p class="auth-sub">创建账号，收藏喜欢的菜并记录浏览历史</p>
    <form class="auth-form" @submit.prevent="onSubmit">
      <label>
        <span>用户名</span>
        <input
          v-model="username"
          data-testid="register-username"
          type="text"
          autocomplete="username"
          placeholder="3-32 个字符"
        />
      </label>
      <label>
        <span>邮箱</span>
        <input
          v-model="email"
          data-testid="register-email"
          type="email"
          autocomplete="email"
          placeholder="name@example.com"
        />
      </label>
      <label>
        <span>密码</span>
        <input
          v-model="password"
          data-testid="register-password"
          type="password"
          autocomplete="new-password"
          placeholder="至少 6 位"
        />
      </label>
      <p v-if="error" class="auth-error" data-testid="register-error">{{ error }}</p>
      <button
        class="auth-btn"
        type="submit"
        data-testid="register-submit"
        :disabled="submitting || auth.loading"
      >
        {{ submitting ? '注册中…' : '注册并登录' }}
      </button>
    </form>
    <p class="auth-switch">
      已有账号？
      <router-link to="/login" data-testid="register-to-login">去登录</router-link>
    </p>
  </div>
</template>

<style scoped>
.auth-page {
  max-width: 420px;
  margin: 40px auto;
  padding: 32px 28px;
  background: var(--card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}
.auth-title {
  font-family: var(--font-title);
  font-size: 28px;
  color: var(--title);
  margin-bottom: 8px;
}
.auth-sub {
  color: var(--secondary);
  font-size: 14px;
  margin-bottom: 24px;
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.auth-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--body);
}
.auth-form input {
  border: 1px solid var(--divider);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  font-size: 15px;
  font-family: var(--font-body);
  background: #fff;
}
.auth-form input:focus {
  outline: 2px solid var(--accent-light);
  border-color: var(--accent);
}
.auth-error {
  color: #c62828;
  font-size: 13px;
}
.auth-btn {
  margin-top: 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  padding: 12px;
  cursor: pointer;
}
.auth-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.auth-switch {
  margin-top: 20px;
  text-align: center;
  font-size: 14px;
  color: var(--secondary);
}
</style>
