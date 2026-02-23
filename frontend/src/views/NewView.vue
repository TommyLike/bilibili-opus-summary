<template>
  <div class="new-view">
    <div class="page-header">
      <router-link to="/" class="back-link">← 返回列表</router-link>
      <h1 class="page-title">新建摘要</h1>
    </div>

    <div class="card">
      <form @submit.prevent="submit" class="form">
        <!-- URL -->
        <div class="form-group">
          <label class="form-label">Bilibili 动态 URL <span class="required">*</span></label>
          <input
            v-model="form.url"
            type="text"
            class="form-input"
            placeholder="https://www.bilibili.com/opus/..."
            :disabled="submitting"
            required
          />
        </div>

        <!-- 高级选项折叠 -->
        <div class="advanced-toggle" @click="showAdvanced = !showAdvanced">
          {{ showAdvanced ? '▾' : '▸' }} 高级选项（Cookie / API Key）
          <span class="hint">若后端 .env 已配置则无需填写</span>
        </div>

        <div v-if="showAdvanced" class="advanced-fields">
          <div class="form-group">
            <label class="form-label">SESSDATA</label>
            <input v-model="form.sessdata" type="password" class="form-input"
              placeholder="留空则使用后端 .env 中的值" :disabled="submitting" />
          </div>
          <div class="form-group">
            <label class="form-label">BILI_JCT</label>
            <input v-model="form.bili_jct" type="password" class="form-input"
              placeholder="可选" :disabled="submitting" />
          </div>
          <div class="form-group">
            <label class="form-label">BUVID3</label>
            <input v-model="form.buvid3" type="text" class="form-input"
              placeholder="可选" :disabled="submitting" />
          </div>
          <div class="form-group">
            <label class="form-label">GEMINI_API_KEY</label>
            <input v-model="form.gemini_api_key" type="password" class="form-input"
              placeholder="留空则使用后端 .env 中的值" :disabled="submitting" />
          </div>
          <div class="form-group form-group--inline">
            <input v-model="form.force" type="checkbox" id="force" :disabled="submitting" />
            <label for="force" class="form-label" style="margin-bottom:0;cursor:pointer">
              强制重新抓取（忽略缓存）
            </label>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="errorMsg" class="error-box">{{ errorMsg }}</div>

        <!-- 任务状态 -->
        <div v-if="taskStatus" class="status-box" :class="`status-box--${taskStatus}`">
          <template v-if="taskStatus === 'pending' || taskStatus === 'running'">
            <span class="spinner"></span>
            {{ taskStatus === 'pending' ? '任务等待中...' : '正在处理，请稍候...' }}
          </template>
          <template v-else-if="taskStatus === 'done'">
            ✅ 处理完成，即将跳转...
          </template>
          <template v-else-if="taskStatus === 'error'">
            ❌ 处理失败：{{ taskError }}
          </template>
        </div>

        <div class="form-actions">
          <button
            type="submit"
            class="btn-primary"
            :disabled="submitting"
          >
            {{ submitting ? '提交中...' : '生成摘要' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createTask, getTask } from '../api/index.js'

const router = useRouter()

const form = ref({
  url: '',
  sessdata: '',
  bili_jct: '',
  buvid3: '',
  gemini_api_key: '',
  force: false,
})

const showAdvanced = ref(false)
const submitting = ref(false)
const errorMsg = ref('')
const taskStatus = ref('')
const taskError = ref('')

let pollTimer = null

async function submit() {
  errorMsg.value = ''
  taskStatus.value = ''
  taskError.value = ''
  submitting.value = true

  try {
    const payload = { url: form.value.url, force: form.value.force }
    if (form.value.sessdata) payload.sessdata = form.value.sessdata
    if (form.value.bili_jct) payload.bili_jct = form.value.bili_jct
    if (form.value.buvid3) payload.buvid3 = form.value.buvid3
    if (form.value.gemini_api_key) payload.gemini_api_key = form.value.gemini_api_key

    const res = await createTask(payload)
    const taskId = res.data.task_id
    taskStatus.value = 'pending'
    startPolling(taskId)
  } catch (e) {
    const msg = e.response?.data?.error || e.message
    errorMsg.value = `提交失败：${msg}`
    submitting.value = false
  }
}

function startPolling(taskId) {
  pollTimer = setInterval(async () => {
    try {
      const res = await getTask(taskId)
      const { status, error, result } = res.data
      taskStatus.value = status

      if (status === 'done') {
        clearInterval(pollTimer)
        submitting.value = false
        // 跳转到详情页
        const summaryId = result?.summary_id
        if (summaryId) {
          setTimeout(() => router.push(`/summary/${summaryId}`), 800)
        }
      } else if (status === 'error') {
        clearInterval(pollTimer)
        taskError.value = error || '未知错误'
        submitting.value = false
      }
    } catch (e) {
      // 网络抖动忽略
    }
  }, 2000)
}
</script>

<style scoped>
.new-view { max-width: 640px; margin: 0 auto; }

.page-header { margin-bottom: 24px; }

.back-link {
  display: inline-block;
  color: #00a1d6;
  text-decoration: none;
  font-size: 14px;
  margin-bottom: 12px;
}

.page-title { font-size: 22px; font-weight: 700; }

.card {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

.form-group { margin-bottom: 18px; }

.form-group--inline { display: flex; align-items: center; gap: 8px; }

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 6px;
  color: #444;
}

.required { color: #e53935; }

.form-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.form-input:focus { border-color: #00a1d6; }
.form-input:disabled { background: #f9f9f9; color: #999; }

.advanced-toggle {
  font-size: 13px;
  color: #00a1d6;
  cursor: pointer;
  margin-bottom: 16px;
  user-select: none;
}
.advanced-toggle .hint {
  color: #999;
  font-size: 12px;
  margin-left: 8px;
}

.advanced-fields {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 18px;
}

.error-box {
  background: #fff3f3;
  border: 1px solid #ffcdd2;
  color: #c62828;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 16px;
}

.status-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 16px;
}
.status-box--pending, .status-box--running {
  background: #e3f2fd;
  color: #1565c0;
}
.status-box--done { background: #e8f5e9; color: #2e7d32; }
.status-box--error { background: #fff3f3; color: #c62828; }

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #90caf9;
  border-top-color: #1565c0;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.form-actions { margin-top: 8px; }

.btn-primary {
  background: #00a1d6;
  color: #fff;
  border: none;
  padding: 10px 28px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover:not(:disabled) { background: #0090c0; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
