<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function onSubmit() {
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  submitting.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-page" data-testid="login-page">
    <h1 class="auth-title">登录食刻</h1>
    <p class="auth-sub">登录后可同步收藏与浏览历史</p>
    <form class="auth-form" @submit.prevent="onSubmit">
      <label>
        <span>用户名</span>
        <input
          v-model="username"
          data-testid="login-username"
          type="text"
          autocomplete="username"
          placeholder="请输入用户名"
        />
      </label>
      <label>
        <span>密码</span>
        <input
          v-model="password"
          data-testid="login-password"
          type="password"
          autocomplete="current-password"
          placeholder="请输入密码"
        />
      </label>
      <p v-if="error" class="auth-error" data-testid="login-error">{{ error }}</p>
      <button
        class="auth-btn"
        type="submit"
        data-testid="login-submit"
        :disabled="submitting || auth.loading"
      >
        {{ submitting ? '登录中…' : '登录' }}
      </button>
    </form>
    <p class="auth-switch">
      还没有账号？
      <router-link to="/register" data-testid="login-to-register">去注册</router-link>
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
