<template>
  <div class="page narrow-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">WRONG QUESTIONS</p>
        <h1>错题本</h1>
        <p>自动收集练习中答错的题目，支持反复复习与斩题。</p>
      </div>
    </header>

    <section v-if="loading" class="paper-panel">
      <el-skeleton :rows="5" animated />
    </section>

    <section v-else-if="questions.length === 0" class="paper-panel empty-state">
      <el-empty description="还没有错题，继续保持！" />
    </section>

    <section v-else class="question-list">
      <div v-for="q in questions" :key="q.question_id" class="paper-panel question-card">
        <div class="question-meta">
          <el-tag size="small" :type="q.type === 'multiple' ? 'warning' : 'primary'">
            {{ typeLabel(q.type) }}
          </el-tag>
          <span class="bank-name">{{ q.bank_name }}</span>
          <span class="wrong-count">错 {{ q.wrong_count }} 次</span>
        </div>
        <h3>{{ q.stem }}</h3>
        <div class="option-list">
          <div
            v-for="option in q.options"
            :key="option.label"
            class="option-item"
            :class="{ correct: q.answer.includes(option.label) }"
          >
            <b>{{ option.label }}</b>{{ option.content }}
          </div>
        </div>
        <div class="question-actions">
          <el-button size="small" @click="toggleExplanation(q)">
            {{ q.showExplanation ? '隐藏解析' : '查看解析' }}
          </el-button>
          <el-button size="small" type="success" @click="master(q)">
            斩题
          </el-button>
        </div>
        <div v-if="q.showExplanation" class="explanation">
          <p><b>正确答案：</b>{{ q.answer.join('、') }}</p>
          <p><b>解析：</b>{{ q.explanation }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { quizApi } from '@/api/modules'

const questions = ref([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const list = (await quizApi.wrongQuestions()).data
    questions.value = list.map((q) => ({ ...q, showExplanation: false }))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载错题失败')
  } finally {
    loading.value = false
  }
}

const toggleExplanation = (q) => {
  q.showExplanation = !q.showExplanation
}

const typeLabel = (type) => {
  const map = { single: '单选题', multiple: '多选题', judgment: '判断题' }
  return map[type] || type
}

const master = async (q) => {
  try {
    await quizApi.master({ question_id: q.question_id, mastered: true })
    ElMessage.success('已斩题')
    questions.value = questions.value.filter((item) => item.question_id !== q.question_id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '斩题失败')
  }
}

onMounted(load)
</script>

<style scoped>
.question-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.question-card h3 {
  margin: var(--space-3) 0;
  font-size: var(--text-lg);
  line-height: 1.6;
}
.question-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--gray-600);
  font-size: var(--text-sm);
}
.bank-name {
  flex: 1;
}
.wrong-count {
  color: var(--danger);
  font-weight: 600;
}
.option-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.option-item {
  padding: var(--space-3);
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-md);
  background: #fff;
}
.option-item.correct {
  border-color: var(--success);
  background: var(--success-bg);
}
.option-item b {
  margin-right: var(--space-2);
}
.question-actions {
  display: flex;
  gap: var(--space-2);
}
.explanation {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--gray-50);
  border-radius: var(--radius-md);
  color: var(--gray-800);
}
</style>
