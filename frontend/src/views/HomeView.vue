<template>
  <div>
    <!-- ===== 新建摘要表单 ===== -->
    <div class="section-label">新建摘要</div>
    <div class="new-card">
      <div class="new-card-accent"></div>
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
          <span class="toggle-arrow">{{ showAdvanced ? '▾' : '▸' }}</span>
          高级选项（Cookie / API Key）
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
            <input v-model="form.force" type="checkbox" id="force" :disabled="submitting" class="form-check" />
            <label for="force" class="form-label form-label--check">
              强制重新抓取（忽略缓存）
            </label>
          </div>
        </div>

        <!-- 邮件通知 -->
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
            <span>✓ 处理完成，即将跳转...</span>
            <span v-if="emailSent === true" class="email-badge email-badge--ok">
              邮件已发送至 {{ form.notifyEmail }}
            </span>
            <span v-else-if="emailSent === false" class="email-badge email-badge--err">
              邮件发送失败：{{ emailError }}
            </span>
          </template>
          <template v-else-if="taskStatus === 'error'">✕ 处理失败：{{ taskError }}</template>
        </div>
      </form>
    </div>

    <!-- ===== 历史摘要 ===== -->
    <div class="history-header">
      <div class="section-label" style="margin-bottom:0">历史摘要</div>
      <input
        v-model="filterText"
        type="text"
        class="filter-input"
        placeholder="搜索..."
      />
    </div>

    <div v-if="loading" class="loading">
      <div class="loading-spinner"></div>
    </div>
    <div v-else-if="loadError" class="error-box">{{ loadError }}</div>
    <div v-else-if="filteredSummaries.length === 0" class="empty">
      <p>{{ filterText ? '没有匹配的摘要' : '暂无摘要记录，在上方输入 URL 立即创建' }}</p>
    </div>

    <div v-else class="grid">
      <router-link
        v-for="(s, i) in filteredSummaries"
        :key="s.id"
        :to="`/summary/${s.id}`"
        class="card"
        :style="{ '--i': i }"
      >
        <div class="card-cover">
          <img
            v-if="s.cover_image_local"
            :src="`/output/${s.id}/${s.cover_image_local}`"
            :alt="s.author"
            class="card-img"
            @error="onImgError"
          />
          <div v-else class="card-placeholder">
            <span class="placeholder-initial">{{ s.author?.[0] || 'B' }}</span>
          </div>
          <div class="card-overlay">
            <span class="card-author">{{ s.author }}</span>
          </div>
        </div>
        <div class="card-body">
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
  e.target.parentElement.innerHTML = '<div class="card-placeholder"><span class="placeholder-initial">B</span></div>'
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
const emailSent = ref(null)
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
/* ---- Section label ---- */
.section-label {
  font-family: 'Playfair Display', serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 16px;
  letter-spacing: 0.01em;
}

/* ---- New summary card ---- */
.new-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 44px;
  overflow: hidden;
}

.new-card-accent {
  height: 2px;
  background: linear-gradient(90deg, var(--accent) 0%, transparent 70%);
}

.form { padding: 22px 24px; }

.form-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.form-input {
  flex: 1;
  padding: 10px 14px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  width: 100%;
  box-sizing: border-box;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.form-input::placeholder { color: var(--text-muted); }
.form-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.form-input:disabled { opacity: 0.45; cursor: not-allowed; }

.btn-primary {
  background: linear-gradient(135deg, #FB7299, #C94060);
  color: white;
  border: none;
  padding: 10px 22px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  font-family: 'Syne', sans-serif;
  cursor: pointer;
  white-space: nowrap;
  letter-spacing: 0.03em;
  transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s;
  flex-shrink: 0;
  box-shadow: 0 2px 12px rgba(251,114,153,0.3);
}
.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 20px rgba(251,114,153,0.42);
}
.btn-primary:active:not(:disabled) { transform: translateY(0); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; }

/* Advanced toggle */
.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
  margin-bottom: 12px;
  padding: 4px 0;
  transition: color 0.15s;
}
.advanced-toggle:hover { color: var(--text); }
.toggle-arrow { color: var(--accent); font-size: 11px; }
.hint { color: var(--text-faint); font-size: 12px; margin-left: 4px; }

.advanced-fields {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 14px;
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
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  margin-bottom: 6px;
  color: var(--text-muted);
}
.form-label--check {
  margin-bottom: 0;
  cursor: pointer;
  text-transform: none;
  letter-spacing: 0;
  font-size: 13px;
}
.form-check { accent-color: var(--accent); }

/* Error / status boxes */
.error-box {
  background: var(--error-bg);
  border: 1px solid rgba(255,82,82,0.15);
  color: #FF8A8A;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-top: 12px;
}

.status-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.status-box--pending,
.status-box--running {
  background: var(--info-bg);
  border: 1px solid rgba(96,165,250,0.15);
  color: #7FB8FF;
}
.status-box--done {
  background: var(--success-bg);
  border: 1px solid rgba(61,201,143,0.15);
  color: #5EDAA8;
}
.status-box--error {
  background: var(--error-bg);
  border: 1px solid rgba(255,82,82,0.15);
  color: #FF8A8A;
}

.spinner {
  display: inline-block;
  width: 13px;
  height: 13px;
  border: 2px solid rgba(127,184,255,0.2);
  border-top-color: #7FB8FF;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Email notification */
.email-notify-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.email-notify-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  white-space: nowrap;
}
.email-notify-input {
  flex: 1;
  min-width: 180px;
  max-width: 300px;
}
.email-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
}
.email-badge--ok {
  background: var(--success-bg);
  color: #5EDAA8;
  border: 1px solid rgba(61,201,143,0.15);
}
.email-badge--err {
  background: rgba(255,147,51,0.08);
  color: #FFB870;
  border: 1px solid rgba(255,147,51,0.15);
}

/* ---- History section ---- */
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  gap: 16px;
}

.filter-input {
  padding: 8px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
  outline: none;
  width: 200px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.filter-input::placeholder { color: var(--text-muted); }
.filter-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.loading {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}
.loading-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.empty {
  text-align: center;
  padding: 80px 0;
  color: var(--text-faint);
  font-size: 14px;
}

/* ---- Card grid ---- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  text-decoration: none;
  color: inherit;
  display: block;
  transition: transform 0.22s ease, border-color 0.22s, box-shadow 0.22s;
  animation: fadeInUp 0.45s ease both;
  animation-delay: calc(var(--i, 0) * 45ms);
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}

.card:hover {
  transform: translateY(-5px);
  border-color: var(--border-hover);
  box-shadow:
    0 16px 40px rgba(0,0,0,0.4),
    0 0 0 1px rgba(251,114,153,0.12);
}

/* Card cover image */
.card-cover {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: var(--surface2);
  overflow: hidden;
}

.card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.38s ease;
}
.card:hover .card-img { transform: scale(1.05); }

.card-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--surface2) 0%, var(--surface3) 100%);
}
.placeholder-initial {
  font-family: 'Playfair Display', serif;
  font-size: 44px;
  font-weight: 700;
  color: var(--text-faint);
  line-height: 1;
}

/* Gradient overlay with author name */
.card-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 30px 14px 12px;
  background: linear-gradient(to top, rgba(0,0,0,0.82) 0%, transparent 100%);
}
.card-author {
  display: block;
  color: rgba(255,255,255,0.92);
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 6px rgba(0,0,0,0.5);
}

/* Card metadata */
.card-body { padding: 11px 14px 14px; }
.card-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 3px;
}
.card-id {
  font-size: 11px;
  color: var(--text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
}
</style>
