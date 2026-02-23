import { ref } from 'vue'

// 全局登录状态，App.vue 和 api/index.js 共享
export const isLoggedIn = ref(false)
export const checkingAuth = ref(true)
