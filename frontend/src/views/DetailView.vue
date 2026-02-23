<template>
  <div class="detail-view">
    <div class="page-header">
      <router-link to="/" class="back-link">
        <span class="back-arrow">←</span> 返回列表
      </router-link>
    </div>

    <div v-if="loading" class="loading">
      <div class="loading-spinner"></div>
    </div>

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

      <!-- 原始图片展示 -->
      <div v-if="summary.images && summary.images.length" class="image-gallery">
        <div class="gallery-title">
          <span class="gallery-icon">◈</span>
          原始图片（共 {{ summary.images.length }} 张）
        </div>
        <div class="gallery-grid">
          <div
            v-for="(img, idx) in summary.images"
            :key="img"
            class="thumb-wrap"
            @click="openLightbox(idx)"
          >
            <img
              :src="`/output/${summary.id}/images/${img}`"
              :alt="`图片 ${idx + 1}`"
              class="thumb"
            />
            <div class="thumb-overlay">
              <span class="thumb-icon">⊕</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 邮件发送卡片 -->
      <div v-if="emailEnabled" class="email-card">
        <div class="email-card-title">发送摘要到邮箱</div>
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

  <!-- Lightbox -->
  <Teleport to="body">
    <div v-if="lightboxOpen" class="lb-overlay" @wheel.prevent="onWheel">
      <button class="lb-close" @click="closeLightbox">✕</button>

      <div class="lb-zoom-bar">
        <button class="lb-zoom-btn" @click="zoomOut" :disabled="zoomScale <= 0.2">−</button>
        <span class="lb-zoom-label">{{ Math.round(zoomScale * 100) }}%</span>
        <button class="lb-zoom-btn" @click="zoomIn" :disabled="zoomScale >= 5">+</button>
        <button class="lb-zoom-btn lb-zoom-reset" @click="resetZoom" title="还原">↺</button>
      </div>

      <div
        class="lb-img-area"
        @mousedown.prevent="startDrag"
        @mousemove="onDrag"
        @mouseup="endDrag"
        @mouseleave="endDrag"
      >
        <img
          :src="`/output/${summary.id}/images/${summary.images[lightboxIndex]}`"
          class="lb-img"
          :alt="`图片 ${lightboxIndex + 1}`"
          :style="imgStyle"
          draggable="false"
          @dblclick="toggleZoom"
        />
      </div>

      <button
        class="lb-arrow lb-arrow--left"
        @click="prevImage"
        :disabled="summary.images.length <= 1"
      >‹</button>
      <button
        class="lb-arrow lb-arrow--right"
        @click="nextImage"
        :disabled="summary.images.length <= 1"
      >›</button>

      <div class="lb-footer">
        <span class="lb-counter">{{ lightboxIndex + 1 }} / {{ summary.images.length }}</span>
        <span class="lb-hint">滚轮缩放 · 拖拽移动 · 双击 2× · Esc 关闭</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { getSummary, sendEmail } from '../api/index.js'
import { emailEnabled } from '../auth.js'

const route = useRoute()
const summary = ref({})
const loading = ref(true)
const error = ref('')

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
    emailResult.value = `✓ 邮件已发送至 ${emailInput.value}`
    emailResultOk.value = true
  } catch (e) {
    emailResult.value = `✕ 发送失败：${e.response?.data?.error || e.message}`
    emailResultOk.value = false
  } finally {
    emailSending.value = false
  }
}

// ---- Lightbox ----
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)

const zoomScale = ref(1)
const panX = ref(0)
const panY = ref(0)
const isDragging = ref(false)
let dragOrigin = null

const imgStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoomScale.value})`,
  transformOrigin: 'center center',
  cursor: isDragging.value ? 'grabbing' : (zoomScale.value > 1 ? 'grab' : 'zoom-in'),
  transition: isDragging.value ? 'none' : 'transform 0.15s ease',
  userSelect: 'none',
}))

function resetZoom() { zoomScale.value = 1; panX.value = 0; panY.value = 0 }
function zoomIn() { zoomScale.value = Math.min(5, parseFloat((zoomScale.value + 0.25).toFixed(2))) }
function zoomOut() {
  zoomScale.value = Math.max(0.2, parseFloat((zoomScale.value - 0.25).toFixed(2)))
  if (zoomScale.value <= 1) { panX.value = 0; panY.value = 0 }
}
function toggleZoom() { if (zoomScale.value !== 1) { resetZoom() } else { zoomScale.value = 2 } }
function onWheel(e) {
  const step = e.deltaY < 0 ? 0.15 : -0.15
  zoomScale.value = Math.min(5, Math.max(0.2, parseFloat((zoomScale.value + step).toFixed(2))))
  if (zoomScale.value <= 1) { panX.value = 0; panY.value = 0 }
}
function startDrag(e) {
  if (zoomScale.value <= 1) return
  isDragging.value = true
  dragOrigin = { x: e.clientX, y: e.clientY, px: panX.value, py: panY.value }
}
function onDrag(e) {
  if (!isDragging.value || !dragOrigin) return
  panX.value = dragOrigin.px + (e.clientX - dragOrigin.x)
  panY.value = dragOrigin.py + (e.clientY - dragOrigin.y)
}
function endDrag() { isDragging.value = false; dragOrigin = null }
function openLightbox(idx) { lightboxIndex.value = idx; resetZoom(); lightboxOpen.value = true }
function closeLightbox() { lightboxOpen.value = false; resetZoom() }
function prevImage() {
  const len = summary.value.images?.length || 0
  if (len <= 1) return
  lightboxIndex.value = (lightboxIndex.value - 1 + len) % len
  resetZoom()
}
function nextImage() {
  const len = summary.value.images?.length || 0
  if (len <= 1) return
  lightboxIndex.value = (lightboxIndex.value + 1) % len
  resetZoom()
}
function onKeydown(e) {
  if (!lightboxOpen.value) return
  if (e.key === 'ArrowLeft')  prevImage()
  else if (e.key === 'ArrowRight') nextImage()
  else if (e.key === 'Escape') closeLightbox()
  else if (e.key === '+' || e.key === '=') zoomIn()
  else if (e.key === '-') zoomOut()
  else if (e.key === '0') resetZoom()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const renderedMd = computed(() => {
  if (!summary.value.summary_md) return ''
  const id = summary.value.id || route.params.id
  const md = summary.value.summary_md.replace(
    /!\[([^\]]*)\]\(images\/([^)]+)\)/g,
    `![$1](/output/${id}/images/$2)`
  )
  return marked.parse(md)
})
</script>

<style scoped>
.detail-view { max-width: 780px; margin: 0 auto; }

/* ---- Back link ---- */
.page-header { margin-bottom: 24px; }

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 13px;
  letter-spacing: 0.02em;
  transition: color 0.15s;
}
.back-link:hover { color: var(--accent); }
.back-arrow { font-size: 16px; line-height: 1; }

/* ---- Loading / error ---- */
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
@keyframes spin { to { transform: rotate(360deg); } }

.error-box {
  text-align: center;
  padding: 60px 0;
  color: #FF8A8A;
  font-size: 15px;
}

/* ---- Content card ---- */
.content {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

/* ---- Meta section ---- */
.meta {
  padding: 22px 28px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  padding-bottom: 18px;
}
.meta-author {
  font-weight: 700;
  font-size: 15px;
  color: var(--text);
  letter-spacing: 0.01em;
}
.meta-sep { color: var(--text-faint); }
.meta-link {
  margin-left: auto;
  color: var(--accent);
  text-decoration: none;
  font-size: 13px;
  transition: opacity 0.15s;
}
.meta-link:hover { opacity: 0.75; }

/* ---- Markdown body ---- */
.markdown-body {
  padding: 28px 28px 32px;
  line-height: 1.78;
  color: var(--text);
  font-size: 15px;
}

.markdown-body :deep(h1) {
  font-family: 'Playfair Display', serif;
  font-size: 24px;
  font-weight: 700;
  margin: 28px 0 14px;
  color: #E0EEFF;
  letter-spacing: 0.01em;
}
.markdown-body :deep(h2) {
  font-family: 'Playfair Display', serif;
  font-size: 19px;
  font-weight: 700;
  margin: 24px 0 12px;
  color: #D4E8FF;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  font-size: 16px;
  font-weight: 600;
  margin: 20px 0 10px;
  color: #C0D8F0;
}
.markdown-body :deep(p) { margin: 12px 0; }
.markdown-body :deep(a) {
  color: var(--accent);
  text-decoration: none;
  transition: opacity 0.15s;
}
.markdown-body :deep(a:hover) { opacity: 0.75; }
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--accent);
  padding: 10px 18px;
  margin: 16px 0;
  background: var(--accent-dim);
  color: var(--text-muted);
  border-radius: 0 8px 8px 0;
}
.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 24px 0;
}
.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 14px 0;
  border: 1px solid var(--border);
}
.markdown-body :deep(code) {
  background: var(--surface2);
  border: 1px solid var(--border);
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 13px;
  color: #A8C8F0;
}
.markdown-body :deep(pre) {
  background: var(--surface2);
  border: 1px solid var(--border);
  padding: 18px 20px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 16px 0;
}
.markdown-body :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
  color: #A8C8F0;
}
.markdown-body :deep(strong) { font-weight: 700; color: #D8EEFF; }
.markdown-body :deep(ul),
.markdown-body :deep(ol) { padding-left: 22px; margin: 10px 0; }
.markdown-body :deep(li) { margin: 5px 0; }

/* ---- Image gallery ---- */
.image-gallery {
  border-top: 1px solid var(--border);
  padding: 20px 28px 24px;
}

.gallery-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.03em;
  margin-bottom: 14px;
  text-transform: uppercase;
}
.gallery-icon { color: var(--accent); font-size: 14px; }

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}

.thumb-wrap {
  position: relative;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 8px;
  cursor: pointer;
  background: var(--surface2);
  border: 1px solid var(--border);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.thumb-wrap:hover {
  border-color: var(--border-hover);
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}

.thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.3s ease;
}
.thumb-wrap:hover .thumb { transform: scale(1.05); }

.thumb-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.thumb-wrap:hover .thumb-overlay { background: rgba(0,0,0,0.35); }
.thumb-icon {
  color: rgba(255,255,255,0);
  font-size: 22px;
  transition: color 0.2s;
}
.thumb-wrap:hover .thumb-icon { color: rgba(255,255,255,0.85); }

/* ---- Email card ---- */
.email-card {
  border-top: 1px solid var(--border);
  padding: 20px 28px 24px;
}

.email-card-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.email-card-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.email-input {
  flex: 1;
  padding: 10px 14px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.email-input::placeholder { color: var(--text-muted); }
.email-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}
.email-input:disabled { opacity: 0.45; }

.btn-send {
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
  box-shadow: 0 2px 12px rgba(251,114,153,0.28);
}
.btn-send:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 18px rgba(251,114,153,0.4);
}
.btn-send:active:not(:disabled) { transform: translateY(0); }
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; }

.email-result {
  margin-top: 10px;
  font-size: 13px;
  padding: 9px 14px;
  border-radius: 8px;
}
.email-result--ok {
  background: var(--success-bg);
  border: 1px solid rgba(61,201,143,0.15);
  color: #5EDAA8;
}
.email-result--err {
  background: var(--error-bg);
  border: 1px solid rgba(255,82,82,0.15);
  color: #FF8A8A;
}

/* ---- Lightbox ---- */
.lb-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(3,8,14,0.94);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.lb-img-area {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.lb-img {
  max-width: 90vw;
  max-height: 82vh;
  object-fit: contain;
  border-radius: 6px;
  box-shadow: 0 16px 60px rgba(0,0,0,0.7);
}

.lb-close {
  position: absolute;
  top: 18px;
  right: 24px;
  z-index: 10;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.7);
  font-size: 18px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}
.lb-close:hover { background: rgba(255,255,255,0.15); color: #fff; }

.lb-zoom-bar {
  position: absolute;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(0,0,0,0.55);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: 5px 10px;
  user-select: none;
  backdrop-filter: blur(8px);
}

.lb-zoom-btn {
  background: rgba(255,255,255,0.1);
  border: none;
  color: rgba(255,255,255,0.8);
  font-size: 18px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  line-height: 1;
}
.lb-zoom-btn:hover:not(:disabled) { background: rgba(255,255,255,0.2); }
.lb-zoom-btn:disabled { opacity: 0.25; cursor: default; }
.lb-zoom-reset { font-size: 15px; }

.lb-zoom-label {
  color: rgba(255,255,255,0.7);
  font-size: 13px;
  min-width: 44px;
  text-align: center;
}

.lb-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 10;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.8);
  font-size: 40px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
  user-select: none;
}
.lb-arrow:hover:not(:disabled) { background: rgba(255,255,255,0.16); color: #fff; }
.lb-arrow:disabled { opacity: 0.2; cursor: default; }
.lb-arrow--left  { left: 20px; }
.lb-arrow--right { right: 20px; }

.lb-footer {
  position: absolute;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  user-select: none;
}

.lb-counter {
  color: rgba(255,255,255,0.7);
  font-size: 13px;
  background: rgba(0,0,0,0.5);
  padding: 3px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.08);
}

.lb-hint {
  color: rgba(255,255,255,0.3);
  font-size: 11px;
}
</style>
