import { ref } from 'vue'

// 全局登录状态，App.vue 和 api/index.js 共享
export const isLoggedIn = ref(false)
export const checkingAuth = ref(true)

// 服务端能力标志：SMTP 是否已配置（App.vue 启动后拉取一次）
export const emailEnabled = ref(false)
