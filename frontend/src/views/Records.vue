<template>
  <div class="page narrow-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">PRACTICE RECORDS</p>
        <h1>练习记录</h1>
        <p>查看你完成的练习，了解每套题库的正确率与进步情况。</p>
      </div>
    </header>

    <section v-if="records.length" class="records-list">
      <article v-for="record in records" :key="record.session_id" class="record-card">
        <div class="record-main">
          <h3>{{ record.bank_name }}</h3>
          <div class="record-meta">
            <span>{{ modeText(record.mode) }}</span>
            <span>{{ record.total_count }} 题</span>
            <span>{{ formatTime(record.finished_at) }}</span>
          </div>
        </div>
        <div class="record-score" :class="scoreClass(record.accuracy)">
          <strong>{{ record.accuracy }}%</strong>
          <span>正确率</span>
        </div>
        <div class="record-actions">
          <el-button type="primary" @click="practice(record.bank_id)">
            再练一次
          </el-button>
        </div>
      </article>
    </section>

    <el-empty v-else-if="!loading" description="还没有练习记录，去题库中心开始练习吧">
      <el-button type="primary" @click="router.push('/banks')">去题库中心</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { quizApi } from '@/api/modules'

const router = useRouter()
const records = ref([])
const loading = ref(true)

const load = async () => {
  loading.value = true
  try {
    const res = await quizApi.sessions()
    records.value = res.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载练习记录失败')
  } finally {
    loading.value = false
  }
}

const modeText = (mode) => (mode === 'random' ? '随机练习' : '顺序练习')

const scoreClass = (accuracy) => {
  if (accuracy >= 80) return 'excellent'
  if (accuracy >= 60) return 'good'
  return 'needs-work'
}

const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const practice = (bankId) => router.push(`/practice/${bankId}`)

onMounted(load)
</script>

<style scoped>
.records-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.record-card {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  background: #fff;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-card);
}

.record-main {
  flex: 1;
  min-width: 0;
}

.record-main h3 {
  margin: 0 0 var(--space-2);
  font: 700 var(--text-lg) var(--font-sans);
  color: var(--gray-900);
}

.record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  color: var(--gray-500);
  font-size: var(--text-sm);
}

.record-score {
  text-align: center;
  min-width: 80px;
}

.record-score strong {
  display: block;
  font: 800 var(--text-3xl) / 1 var(--font-sans);
  color: var(--gray-900);
}

.record-score span {
  font-size: var(--text-xs);
  color: var(--gray-500);
}

.record-score.excellent strong { color: var(--success); }
.record-score.good strong { color: var(--warning); }
.record-score.needs-work strong { color: var(--danger); }

@media (max-width: 768px) {
  .record-card {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-4);
  }

  .record-score {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }

  .record-score span {
    font-size: var(--text-sm);
  }

  .record-actions {
    width: 100%;
  }

  .record-actions .el-button {
    width: 100%;
  }
}
</style>
