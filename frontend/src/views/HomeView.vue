<template>
  <div>
    <!-- ===== 新建摘要表单 ===== -->
    <div class="section-title">新建摘要</div>
    <div class="new-card">
      <form @submit.prevent="submit" class="form">
        <div class="form-row">
          <input
            v-model="form.url"
            type="text"
            class="form-input"
            placeholder="Bilibili 动态 URL，如 https://www.bilibili.com/opus/... 或 https://t.bilibili.com/..."
            :disabled="submitting"
            required
          />
          <button type="submit" class="btn-primary" :disabled="submitting">
            {{ submitting ? '处理中...' : '生成摘要' }}
          </button>
        </div>

        <!-- 高级选项 -->
        <div class="advanced-toggle" @click="showAdvanced = !showAdvanced">
          {{ showAdvanced ? '▾' : '▸' }} 高级选项（Cookie / API Key）
          <span class="hint">若后端 .env 已配置则无需填写</span>
        </div>
        <div v-if="showAdvanced" class="advanced-fields">
          <div class="adv-row">
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
          </div>
          <div class="form-group form-group--inline">
            <input v-model="form.force" type="checkbox" id="force" :disabled="submitting" />
            <label for="force" class="form-label" style="margin-bottom:0;cursor:pointer">
              强制重新抓取（忽略缓存）
            </label>
          </div>
        </div>

        <!-- 邮件通知（SMTP 已配置时显示） -->
        <div v-if="emailEnabled" class="email-notify-row">
          <label class="email-notify-check">
            <input v-model="form.notifyEmailEnabled" type="checkbox" :disabled="submitting" />
            生成后发送邮件通知
          </label>
          <input
            v-if="form.notifyEmailEnabled"
            v-model="form.notifyEmail"
            type="email"
            class="form-input email-notify-input"
            placeholder="收件邮箱"
            :disabled="submitting"
            required
          />
        </div>

        <!-- 错误 / 状态 -->
        <div v-if="errorMsg" class="error-box">{{ errorMsg }}</div>
        <div v-if="taskStatus" class="status-box" :class="`status-box--${taskStatus}`">
          <template v-if="taskStatus === 'pending' || taskStatus === 'running'">
            <span class="spinner"></span>
            {{ taskStatus === 'pending' ? '任务等待中...' : '正在处理，请稍候...' }}
          </template>
          <template v-else-if="taskStatus === 'done'">
            <span>✅ 处理完成，即将跳转...</span>
            <span v-if="emailSent === true" class="email-badge email-badge--ok">
              📧 邮件已发送至 {{ form.notifyEmail }}
            </span>
            <span v-else-if="emailSent === false" class="email-badge email-badge--err">
              ⚠️ 邮件发送失败：{{ emailError }}
            </span>
          </template>
          <template v-else-if="taskStatus === 'error'">❌ 处理失败：{{ taskError }}</template>
        </div>
      </form>
    </div>

    <!-- ===== 历史摘要 ===== -->
    <div class="history-header">
      <div class="section-title" style="margin-bottom:0">历史摘要</div>
      <input
        v-model="filterText"
        type="text"
        class="filter-input"
        placeholder="按名称筛选..."
      />
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="loadError" class="error-box">{{ loadError }}</div>
    <div v-else-if="filteredSummaries.length === 0" class="empty">
      <p>{{ filterText ? '没有匹配的摘要' : '暂无摘要记录，在上方输入 URL 立即创建' }}</p>
    </div>

    <div v-else class="grid">
      <router-link
        v-for="s in filteredSummaries"
        :key="s.id"
        :to="`/summary/${s.id}`"
        class="card"
      >
        <div class="card-cover">
          <img
            v-if="s.cover_image_local"
            :src="`/output/${s.id}/${s.cover_image_local}`"
            :alt="s.author"
            class="card-img"
            @error="onImgError"
          />
          <div v-else class="card-placeholder"><span>📄</span></div>
        </div>
        <div class="card-body">
          <div class="card-author">{{ s.author }}</div>
          <div class="card-time">{{ s.time || s.fetched_at?.slice(0, 10) }}</div>
          <div class="card-id">{{ s.id }}</div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSummaries, createTask, getTask } from '../api/index.js'
import { emailEnabled } from '../auth.js'

const router = useRouter()

// ---- 历史摘要 ----
const summaries = ref([])
const loading = ref(true)
const loadError = ref('')
const filterText = ref('')

const filteredSummaries = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return summaries.value
  return summaries.value.filter(s =>
    (s.author || '').toLowerCase().includes(q) ||
    (s.id || '').toLowerCase().includes(q)
  )
})

async function loadSummaries() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getSummaries()
    summaries.value = res.data
  } catch (e) {
    loadError.value = `加载失败：${e.message}`
  } finally {
    loading.value = false
  }
}

onMounted(loadSummaries)

function onImgError(e) {
  e.target.style.display = 'none'
  e.target.parentElement.innerHTML = '<div class="card-placeholder"><span>📄</span></div>'
}

// ---- 新建摘要 ----
const form = ref({
  url: '',
  sessdata: '',
  bili_jct: '',
  buvid3: '',
  gemini_api_key: '',
  force: false,
  notifyEmailEnabled: false,
  notifyEmail: '',
})
const showAdvanced = ref(false)
const submitting = ref(false)
const errorMsg = ref('')
const taskStatus = ref('')
const taskError = ref('')
const emailSent = ref(null)   // null=未触发, true=已发送, false=发送失败
const emailError = ref('')
let pollTimer = null

async function submit() {
  errorMsg.value = ''
  taskStatus.value = ''
  taskError.value = ''
  emailSent.value = null
  emailError.value = ''
  submitting.value = true

  try {
    const payload = { url: form.value.url, force: form.value.force }
    if (form.value.sessdata) payload.sessdata = form.value.sessdata
    if (form.value.bili_jct) payload.bili_jct = form.value.bili_jct
    if (form.value.buvid3) payload.buvid3 = form.value.buvid3
    if (form.value.gemini_api_key) payload.gemini_api_key = form.value.gemini_api_key
    if (form.value.notifyEmailEnabled && form.value.notifyEmail) {
      payload.notify_email = form.value.notifyEmail
    }

    const res = await createTask(payload)
    taskStatus.value = 'pending'
    startPolling(res.data.task_id)
  } catch (e) {
    errorMsg.value = `提交失败：${e.response?.data?.error || e.message}`
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
        if (res.data.email_sent !== undefined) {
          emailSent.value = res.data.email_sent
          emailError.value = res.data.email_error || ''
        }
        const summaryId = result?.summary_id
        if (summaryId) {
          setTimeout(() => router.push(`/summary/${summaryId}`), 1500)
        }
      } else if (status === 'error') {
        clearInterval(pollTimer)
        taskError.value = error || '未知错误'
        submitting.value = false
      }
    } catch (_) { /* 网络抖动忽略 */ }
  }, 2000)
}
</script>

<style scoped>
.section-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 14px;
  color: #222;
}

/* ---- 新建表单 ---- */
.new-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  margin-bottom: 32px;
}

.form-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.form-input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}
.form-input:focus { border-color: #00a1d6; }
.form-input:disabled { background: #f9f9f9; color: #999; }

.btn-primary {
  background: #00a1d6;
  color: #fff;
  border: none;
  padding: 10px 22px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
  flex-shrink: 0;
}
.btn-primary:hover:not(:disabled) { background: #0090c0; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.advanced-toggle {
  font-size: 13px;
  color: #00a1d6;
  cursor: pointer;
  user-select: none;
  margin-bottom: 12px;
}
.advanced-toggle .hint { color: #999; font-size: 12px; margin-left: 8px; }

.advanced-fields {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}
.adv-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.form-group { margin-bottom: 0; }
.form-group--inline { display: flex; align-items: center; gap: 8px; }
.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 5px;
  color: #555;
}

.error-box {
  background: #fff3f3;
  border: 1px solid #ffcdd2;
  color: #c62828;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  margin-top: 10px;
}

.status-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  margin-top: 10px;
}
.status-box--pending, .status-box--running { background: #e3f2fd; color: #1565c0; }
.status-box--done { background: #e8f5e9; color: #2e7d32; }
.status-box--error { background: #fff3f3; color: #c62828; }

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #90caf9;
  border-top-color: #1565c0;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ---- 历史摘要 ---- */
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 16px;
}

.filter-input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  width: 220px;
  transition: border-color 0.15s;
}
.filter-input:focus { border-color: #00a1d6; }

.loading, .empty {
  text-align: center;
  padding: 60px 0;
  color: #888;
  font-size: 15px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
}

.card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  text-decoration: none;
  color: inherit;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  transition: transform 0.15s, box-shadow 0.15s;
  display: block;
}
.card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.card-cover {
  width: 100%;
  aspect-ratio: 16/9;
  background: #f0f0f0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-img { width: 100%; height: 100%; object-fit: cover; }
.card-placeholder {
  font-size: 40px;
  color: #ccc;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-body { padding: 12px 16px; }
.card-author {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-time { font-size: 12px; color: #999; margin-bottom: 4px; }
.card-id {
  font-size: 11px;
  color: #bbb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---- 邮件通知 ---- */
.email-notify-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.email-notify-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  white-space: nowrap;
}

.email-notify-input {
  flex: 1;
  min-width: 180px;
  max-width: 300px;
}

.email-badge {
  font-size: 13px;
  padding: 3px 10px;
  border-radius: 12px;
  white-space: nowrap;
}
.email-badge--ok { background: #e8f5e9; color: #2e7d32; }
.email-badge--err { background: #fff3e0; color: #e65100; }
</style>
