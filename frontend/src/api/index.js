import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  timeout: 30000,
})

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
