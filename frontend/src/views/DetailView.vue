<template>
  <div class="detail-view">
    <div class="page-header">
      <router-link to="/" class="back-link">← 返回列表</router-link>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="error" class="error-box">{{ error }}</div>

    <div v-else class="content">
      <!-- 元信息 -->
      <div class="meta">
        <span class="meta-author">{{ summary.author }}</span>
        <span class="meta-sep">·</span>
        <span class="meta-time">{{ summary.time }}</span>
        <a
          v-if="summary.source_url"
          :href="summary.source_url"
          target="_blank"
          rel="noopener"
          class="meta-link"
        >查看原动态 ↗</a>
      </div>

      <!-- Markdown 渲染 -->
      <div class="markdown-body" v-html="renderedMd"></div>

      <!-- 邮件发送卡片（SMTP 已配置时显示） -->
      <div v-if="emailEnabled" class="email-card">
        <div class="email-card-title">📧 发送摘要到邮箱</div>
        <div class="email-card-row">
          <input
            v-model="emailInput"
            type="email"
            class="email-input"
            placeholder="输入收件邮箱"
            :disabled="emailSending"
          />
          <button class="btn-send" :disabled="emailSending || !emailInput" @click="handleSendEmail">
            {{ emailSending ? '发送中...' : '发送' }}
          </button>
        </div>
        <div v-if="emailResult" class="email-result" :class="emailResultOk ? 'email-result--ok' : 'email-result--err'">
          {{ emailResult }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { getSummary, sendEmail } from '../api/index.js'
import { emailEnabled } from '../auth.js'

const route = useRoute()
const summary = ref({})
const loading = ref(true)
const error = ref('')

// 用 watch + immediate 替代 onMounted：
// 直接访问 URL 时 route.params.id 可能在初始导航完成后才就绪，
// watch 会在参数可用时自动触发，避免 onMounted 时拿到 undefined 导致 404。
watch(
  () => route.params.id,
  async (id) => {
    if (!id) return
    loading.value = true
    error.value = ''
    summary.value = {}
    try {
      const res = await getSummary(id)
      summary.value = res.data
    } catch (e) {
      error.value = e.response?.status === 404
        ? '摘要不存在'
        : `加载失败：${e.message}`
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)

// ---- 邮件发送 ----
const emailInput = ref('')
const emailSending = ref(false)
const emailResult = ref('')
const emailResultOk = ref(false)

async function handleSendEmail() {
  if (!emailInput.value) return
  emailSending.value = true
  emailResult.value = ''
  try {
    const id = summary.value.id || route.params.id
    await sendEmail(id, emailInput.value)
    emailResult.value = `✅ 邮件已发送至 ${emailInput.value}`
    emailResultOk.value = true
  } catch (e) {
    emailResult.value = `❌ 发送失败：${e.response?.data?.error || e.message}`
    emailResultOk.value = false
  } finally {
    emailSending.value = false
  }
}

const renderedMd = computed(() => {
  if (!summary.value.summary_md) return ''
  const id = summary.value.id || route.params.id
  // 将 markdown 中的相对图片路径重写为绝对路径
  const md = summary.value.summary_md.replace(
    /!\[([^\]]*)\]\(images\/([^)]+)\)/g,
    `![$1](/output/${id}/images/$2)`
  )
  return marked.parse(md)
})
</script>

<style scoped>
.detail-view { max-width: 780px; margin: 0 auto; }

.page-header { margin-bottom: 20px; }

.back-link {
  display: inline-block;
  color: #00a1d6;
  text-decoration: none;
  font-size: 14px;
}

.loading, .error-box {
  text-align: center;
  padding: 60px 0;
  color: #888;
  font-size: 15px;
}
.error-box { color: #e53935; }

.content {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

.meta {
  padding: 20px 28px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 14px;
  color: #666;
}
.meta-author { font-weight: 600; color: #333; }
.meta-sep { color: #ccc; }
.meta-link {
  margin-left: auto;
  color: #00a1d6;
  text-decoration: none;
  font-size: 13px;
}
.meta-link:hover { text-decoration: underline; }

.markdown-body {
  padding: 24px 28px 32px;
  line-height: 1.75;
  color: #333;
  font-size: 15px;
}

/* Markdown 样式 */
.markdown-body :deep(h1) { font-size: 22px; margin: 24px 0 12px; }
.markdown-body :deep(h2) { font-size: 18px; margin: 20px 0 10px; border-bottom: 1px solid #eee; padding-bottom: 6px; }
.markdown-body :deep(h3), .markdown-body :deep(h4) { font-size: 16px; margin: 16px 0 8px; }
.markdown-body :deep(p) { margin: 12px 0; }
.markdown-body :deep(blockquote) {
  border-left: 4px solid #00a1d6;
  padding: 8px 16px;
  margin: 12px 0;
  background: #f0f9ff;
  color: #555;
  border-radius: 0 6px 6px 0;
}
.markdown-body :deep(hr) { border: none; border-top: 1px solid #eee; margin: 20px 0; }
.markdown-body :deep(img) { max-width: 100%; border-radius: 8px; margin: 12px 0; }
.markdown-body :deep(code) {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}
.markdown-body :deep(pre) {
  background: #f5f5f5;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}
.markdown-body :deep(pre code) { background: none; padding: 0; }
.markdown-body :deep(strong) { font-weight: 700; }

/* ---- 邮件发送卡片 ---- */
.email-card {
  border-top: 1px solid #eee;
  padding: 20px 28px 24px;
}

.email-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #555;
  margin-bottom: 12px;
}

.email-card-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.email-input {
  flex: 1;
  padding: 9px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.email-input:focus { border-color: #00a1d6; }
.email-input:disabled { background: #f9f9f9; }

.btn-send {
  background: #00a1d6;
  color: #fff;
  border: none;
  padding: 9px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
  flex-shrink: 0;
}
.btn-send:hover:not(:disabled) { background: #0090c0; }
.btn-send:disabled { opacity: 0.6; cursor: not-allowed; }

.email-result {
  margin-top: 10px;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 6px;
}
.email-result--ok { background: #e8f5e9; color: #2e7d32; }
.email-result--err { background: #fff3f3; color: #c62828; }
</style>
