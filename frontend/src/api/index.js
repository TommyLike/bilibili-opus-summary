import axios from 'axios'
import { isLoggedIn } from '../auth.js'

const api = axios.create({
  baseURL: '/',
  timeout: 30000,
  withCredentials: true,
})

// Session 过期时自动切回登录界面（排除 auth 自身的路由）
api.interceptors.response.use(
  res => res,
  err => {
    if (
      err.response?.status === 401 &&
      !err.config.url.startsWith('/api/auth/')
    ) {
      isLoggedIn.value = false
    }
    return Promise.reject(err)
  }
)

// ---- 鉴权 ----

export function checkAuth() {
  return api.get('/api/auth/check')
}

export function login(password) {
  return api.post('/api/auth/login', { password })
}

export function logout() {
  return api.post('/api/auth/logout')
}

// ---- 业务 API ----

export function getSummaries() {
  return api.get('/api/summaries')
}

export function getSummary(id) {
  return api.get(`/api/summaries/${id}`)
}

export function createTask(payload) {
  return api.post('/api/tasks', payload)
}

export function getTask(taskId) {
  return api.get(`/api/tasks/${taskId}`)
}
