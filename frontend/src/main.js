import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.js'

const app = createApp(App)
app.use(router)
// 等待初始导航完成再挂载，避免直接访问详情 URL 时 route.params 还未就绪
router.isReady().then(() => app.mount('#app'))
