<template>
  <div class="app-layout">
    <header class="app-header">
      <router-link to="/" class="logo">食<span>刻</span></router-link>
      <nav>
        <router-link to="/" class="nav-link">首页</router-link>
        <router-link to="/about" class="nav-link">关于</router-link>
      </nav>
      <div class="nav-avatar">大</div>
    </header>
    <main class="app-main">
      <router-view />
    </main>
    <footer class="app-footer">
      <span class="footer-left">食刻 · 让每一顿都有道理</span>
      <div class="footer-links">
        <router-link to="/about">关于</router-link>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  height: 64px;
  background: rgba(252, 248, 242, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--divider);
}

.app-header .logo {
  font-family: var(--font-title);
  font-size: 24px;
  font-weight: 700;
  color: var(--title);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
}

.app-header .logo span {
  color: var(--accent);
}

.app-header nav {
  display: flex;
  gap: 32px;
  align-items: center;
}

.nav-link {
  color: var(--body);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.2s;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: var(--accent);
}

.nav-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #E67E22, #F39C12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.app-main {
  flex: 1;
  max-width: 1120px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 24px 80px;
}

.app-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 48px;
  border-top: 1px solid var(--divider);
  font-size: 13px;
  color: var(--secondary);
}

.footer-links {
  display: flex;
  gap: 20px;
  align-items: center;
}

.footer-links a {
  font-size: 13px;
  color: var(--secondary);
  text-decoration: none;
  transition: color 0.2s;
}

.footer-links a:hover {
  color: var(--accent);
}

@media (max-width: 640px) {
  .app-header {
    padding: 0 16px;
  }
  .app-main {
    padding: 16px 12px 60px;
  }
  .app-footer {
    padding: 16px;
  }
}
</style>
