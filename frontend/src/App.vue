<template>
  <div id="app">

    <!-- Auth loading -->
    <div v-if="checkingAuth" class="auth-loading">
      <div class="auth-spinner"></div>
    </div>

    <!-- Login page -->
    <div v-else-if="!isLoggedIn" class="login-page">
      <div class="login-glow"></div>
      <div class="login-card">
        <div class="login-logo-wrap">
          <span class="login-logo-b">B</span>
        </div>
        <h1 class="login-title">动态摘要助手</h1>
        <p class="login-sub">Bilibili 内容智能提炼</p>
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

    <!-- Main app -->
    <template v-else>
      <header class="header">
        <div class="header-inner">
          <router-link to="/" class="logo">
            <span class="logo-b">B</span>
            <span class="logo-name">动态摘要</span>
          </router-link>
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
:root {
  --bg: #07111B;
  --bg2: #0B1826;
  --surface: #0D1E30;
  --surface2: #122640;
  --surface3: #162E4A;
  --border: rgba(255,255,255,0.06);
  --border-hover: rgba(251,114,153,0.25);
  --text: #C8E0F5;
  --text-muted: #527A99;
  --text-faint: #2A4A68;
  --accent: #FB7299;
  --accent-glow: rgba(251,114,153,0.18);
  --accent-dim: rgba(251,114,153,0.07);
  --success: #3DC98F;
  --success-bg: rgba(61,201,143,0.08);
  --error: #FF5252;
  --error-bg: rgba(255,82,82,0.08);
  --info-bg: rgba(96,165,250,0.08);
  --radius: 12px;
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html { scroll-behavior: smooth; }

body {
  font-family: 'Syne', -apple-system, 'PingFang SC', '微软雅黑', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Film grain texture */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.032;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.78' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='400' height='400' filter='url(%23n)'/%3E%3C/svg%3E");
  background-repeat: repeat;
  background-size: 400px;
}

#app { display: flex; flex-direction: column; min-height: 100vh; }

/* ---- Auth loading ---- */
.auth-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}

.auth-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ---- Login page ---- */
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

.login-glow {
  position: absolute;
  top: -20%;
  right: -15%;
  width: 55vw;
  height: 55vw;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(251,114,153,0.065) 0%, transparent 65%);
  pointer-events: none;
}

.login-card {
  position: relative;
  z-index: 1;
  background: rgba(13,30,48,0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 48px 44px 42px;
  width: 100%;
  max-width: 380px;
  text-align: center;
  box-shadow: 0 32px 80px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(251,114,153,0.04);
}

.login-logo-wrap { margin-bottom: 22px; }

.login-logo-b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 54px;
  height: 54px;
  background: linear-gradient(135deg, #FB7299, #C94060);
  color: white;
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 28px;
  border-radius: 15px;
  box-shadow: 0 6px 24px rgba(251,114,153,0.42);
}

.login-title {
  font-family: 'Playfair Display', serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 6px;
  letter-spacing: 0.01em;
}

.login-sub {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 32px;
  letter-spacing: 0.02em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.login-input {
  width: 100%;
  padding: 13px 16px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  text-align: center;
  letter-spacing: 0.15em;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.login-input::placeholder { letter-spacing: 0; color: var(--text-muted); }
.login-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.login-input:disabled { opacity: 0.5; cursor: not-allowed; }

.login-error {
  background: var(--error-bg);
  border: 1px solid rgba(255,82,82,0.18);
  color: #FF8A8A;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  text-align: left;
}

.login-btn {
  background: linear-gradient(135deg, #FB7299 0%, #C94060 100%);
  color: white;
  border: none;
  padding: 13px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  font-family: 'Syne', sans-serif;
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s;
  box-shadow: 0 4px 20px rgba(251,114,153,0.35);
}
.login-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 8px 28px rgba(251,114,153,0.45);
}
.login-btn:active:not(:disabled) { transform: translateY(0); }
.login-btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }

/* ---- Header ---- */
.header {
  background: rgba(7,17,27,0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  max-width: 1160px;
  margin: 0 auto;
  padding: 0 28px;
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.logo-b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: var(--accent);
  color: white;
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  font-size: 16px;
  border-radius: 8px;
  flex-shrink: 0;
  box-shadow: 0 2px 10px rgba(251,114,153,0.3);
}

.logo-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: 0.02em;
}

.btn-logout {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-family: 'Syne', sans-serif;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}
.btn-logout:hover {
  border-color: rgba(255,255,255,0.12);
  color: var(--text);
  background: var(--surface);
}

/* ---- Main content ---- */
.main {
  flex: 1;
  max-width: 1160px;
  margin: 0 auto;
  padding: 36px 28px;
  width: 100%;
}
</style>
