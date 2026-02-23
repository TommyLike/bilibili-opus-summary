<template>
  <div id="app">

    <!-- 初始鉴权检查中 -->
    <div v-if="checkingAuth" class="auth-loading">
      <div class="auth-spinner"></div>
    </div>

    <!-- 未登录：全屏登录界面 -->
    <div v-else-if="!isLoggedIn" class="login-page">
      <div class="login-card">
        <div class="login-logo">📺</div>
        <h1 class="login-title">Bilibili 动态摘要助手</h1>
        <form @submit.prevent="handleLogin" class="login-form">
          <input
            v-model="password"
            type="password"
            class="login-input"
            placeholder="请输入访问密码"
            :disabled="logging"
            autofocus
          />
          <div v-if="loginError" class="login-error">{{ loginError }}</div>
          <button type="submit" class="login-btn" :disabled="logging">
            {{ logging ? '验证中...' : '进入' }}
          </button>
        </form>
      </div>
    </div>

    <!-- 已登录：正常应用 -->
    <template v-else>
      <header class="header">
        <div class="header-inner">
          <router-link to="/" class="logo">Bilibili动态内容摘要助手</router-link>
          <button class="btn-logout" @click="handleLogout">退出登录</button>
        </div>
      </header>
      <main class="main">
        <router-view />
      </main>
    </template>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { isLoggedIn, checkingAuth, emailEnabled } from './auth.js'
import { checkAuth, login, logout, getConfig } from './api/index.js'

const password = ref('')
const loginError = ref('')
const logging = ref(false)

onMounted(async () => {
  try {
    await checkAuth()
    isLoggedIn.value = true
    // 拉取服务端能力配置（SMTP 是否启用等）
    try {
      const cfg = await getConfig()
      emailEnabled.value = cfg.data.email_enabled ?? false
    } catch (_) { /* SMTP 未配置时静默降级 */ }
  } catch {
    isLoggedIn.value = false
  } finally {
    checkingAuth.value = false
  }
})

async function handleLogin() {
  loginError.value = ''
  logging.value = true
  try {
    await login(password.value)
    isLoggedIn.value = true
    password.value = ''
  } catch (e) {
    loginError.value = e.response?.data?.error || '登录失败，请重试'
  } finally {
    logging.value = false
  }
}

async function handleLogout() {
  try { await logout() } catch (_) { /* ignore */ }
  isLoggedIn.value = false
}
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f5f5f5;
  color: #333;
  min-height: 100vh;
}

#app { display: flex; flex-direction: column; min-height: 100vh; }

/* ---- 初始加载 ---- */
.auth-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}

.auth-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e0e0e0;
  border-top-color: #00a1d6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ---- 登录页 ---- */
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f5f5f5;
}

.login-card {
  background: #fff;
  border-radius: 16px;
  padding: 40px 40px 36px;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.10);
  text-align: center;
}

.login-logo {
  font-size: 40px;
  margin-bottom: 12px;
}

.login-title {
  font-size: 18px;
  font-weight: 700;
  color: #222;
  margin-bottom: 28px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.login-input {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.15s;
  text-align: center;
  letter-spacing: 0.1em;
}
.login-input:focus { border-color: #00a1d6; }
.login-input:disabled { background: #f9f9f9; }

.login-error {
  background: #fff3f3;
  border: 1px solid #ffcdd2;
  color: #c62828;
  padding: 9px 14px;
  border-radius: 8px;
  font-size: 13px;
}

.login-btn {
  background: #00a1d6;
  color: #fff;
  border: none;
  padding: 11px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.login-btn:hover:not(:disabled) { background: #0090c0; }
.login-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* ---- 主应用 Header ---- */
.header {
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  color: #00a1d6;
  text-decoration: none;
}

.btn-logout {
  background: none;
  border: 1px solid #ddd;
  color: #666;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.btn-logout:hover { background: #f5f5f5; color: #333; }

/* ---- 主内容区 ---- */
.main {
  flex: 1;
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
  width: 100%;
}
</style>
