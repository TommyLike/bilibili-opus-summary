<template>
  <div id="app">
    <header class="header">
      <div class="header-inner">
        <router-link to="/" class="logo">Bilibili动态内容摘要助手</router-link>
      </div>
    </header>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f5f5f5;
  color: #333;
  min-height: 100vh;
}

#app { display: flex; flex-direction: column; min-height: 100vh; }

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

nav { display: flex; gap: 16px; align-items: center; }

.nav-link {
  text-decoration: none;
  color: #555;
  font-size: 14px;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background 0.15s;
}
.nav-link:hover { background: #f0f0f0; color: #333; }
.nav-link--primary {
  background: #00a1d6;
  color: #fff !important;
}
.nav-link--primary:hover { background: #0090c0; }

.main {
  flex: 1;
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
  width: 100%;
}
</style>
