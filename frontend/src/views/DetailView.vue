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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { getSummary } from '../api/index.js'

const route = useRoute()
const summary = ref({})
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const res = await getSummary(route.params.id)
    summary.value = res.data
  } catch (e) {
    error.value = e.response?.status === 404
      ? '摘要不存在'
      : `加载失败：${e.message}`
  } finally {
    loading.value = false
  }
})

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
</style>
