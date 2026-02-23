<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">历史摘要</h1>
      <router-link to="/new" class="btn-primary">+ 新建摘要</router-link>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="error" class="error-box">{{ error }}</div>

    <div v-else-if="summaries.length === 0" class="empty">
      <p>暂无摘要记录</p>
      <router-link to="/new" class="btn-primary" style="margin-top:16px;display:inline-block">
        立即创建第一条摘要
      </router-link>
    </div>

    <div v-else class="grid">
      <router-link
        v-for="s in summaries"
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
          <div v-else class="card-placeholder">
            <span>📄</span>
          </div>
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
import { ref, onMounted } from 'vue'
import { getSummaries } from '../api/index.js'

const summaries = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const res = await getSummaries()
    summaries.value = res.data
  } catch (e) {
    error.value = `加载失败：${e.message}`
  } finally {
    loading.value = false
  }
})

function onImgError(e) {
  e.target.style.display = 'none'
  e.target.parentElement.innerHTML = '<div class="card-placeholder"><span>📄</span></div>'
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title { font-size: 22px; font-weight: 700; }

.btn-primary {
  background: #00a1d6;
  color: #fff;
  padding: 8px 18px;
  border-radius: 8px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}
.btn-primary:hover { background: #0090c0; }

.loading, .error-box, .empty {
  text-align: center;
  padding: 60px 0;
  color: #888;
  font-size: 15px;
}
.error-box { color: #e53935; }

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

.card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

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

.card-time {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.card-id {
  font-size: 11px;
  color: #bbb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
