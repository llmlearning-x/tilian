<template>
  <div class="page narrow-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">WRONG QUESTIONS</p>
        <h1>错题本</h1>
        <p>自动收集练习中答错的题目，支持按题库管理与批量复习。</p>
      </div>
    </header>

    <div class="view-tabs">
      <el-radio-group v-model="viewMode" size="large" @change="onViewModeChange">
        <el-radio-button value="banks">按题库查看</el-radio-button>
        <el-radio-button value="all">全部错题</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 题库视图 -->
    <section v-if="viewMode === 'banks'">
      <div v-if="loadingBanks" class="paper-panel">
        <el-skeleton :rows="4" animated />
      </div>
      <div v-else-if="banks.length === 0" class="paper-panel empty-state">
        <el-empty description="还没有错题，继续保持！" />
      </div>
      <div v-else class="bank-grid">
        <el-card
          v-for="bank in banks"
          :key="bank.bank_id"
          shadow="hover"
          class="bank-card"
          @click="enterBank(bank.bank_id)"
        >
          <div class="bank-card-content">
            <div class="bank-card-header">
              <h3>{{ bank.bank_name }}</h3>
              <el-button
                type="danger"
                text
                size="small"
                @click.stop="deleteBank(bank)"
              >
                删除
              </el-button>
            </div>
            <div class="bank-stats">
              <div class="stat-item">
                <strong>{{ bank.pending_count }}</strong>
                <span>待复习</span>
              </div>
              <div class="stat-item">
                <strong>{{ bank.mastered_count }}</strong>
                <span>已掌握</span>
              </div>
              <div class="stat-item">
                <strong>{{ bank.wrong_count }}</strong>
                <span>总错题</span>
              </div>
            </div>
            <p class="bank-time">最近答错：{{ formatTime(bank.last_wrong_at) }}</p>
          </div>
        </el-card>
      </div>
    </section>

    <!-- 全部错题视图 -->
    <section v-else>
      <div class="filter-bar paper-panel">
        <div class="filter-row">
          <el-select v-model="filters.bank_id" placeholder="全部题库" clearable @change="onFilterChange">
            <el-option
              v-for="bank in bankOptions"
              :key="bank.bank_id"
              :label="bank.bank_name"
              :value="bank.bank_id"
            />
          </el-select>
          <el-select v-model="filters.type" placeholder="全部题型" clearable @change="onFilterChange">
            <el-option label="单选题" value="single" />
            <el-option label="多选题" value="multiple" />
            <el-option label="判断题" value="judgment" />
          </el-select>
          <el-select v-model="filters.min_wrong_count" placeholder="错误次数" clearable @change="onFilterChange">
            <el-option label="1 次" :value="1" />
            <el-option label="2 次及以上" :value="2" />
            <el-option label="3 次及以上" :value="3" />
          </el-select>
          <el-select v-model="filters.last_result" placeholder="最近结果" clearable @change="onFilterChange">
            <el-option label="最近答错" value="wrong" />
            <el-option label="最近答对" value="correct" />
          </el-select>
        </div>
        <div class="filter-row">
          <el-input
            v-model="filters.keyword"
            placeholder="搜索题干关键词"
            clearable
            style="width: 240px"
            @keyup.enter="onFilterChange"
            @clear="onFilterChange"
          />
          <el-select v-model="filters.sort_by" placeholder="排序方式" @change="onFilterChange">
            <el-option label="最近答错时间" value="last_answer_at" />
            <el-option label="错误次数" value="wrong_count" />
            <el-option label="正确次数" value="correct_count" />
          </el-select>
          <el-radio-group v-model="filters.order" size="small" @change="onFilterChange">
            <el-radio-button value="desc">降序</el-radio-button>
            <el-radio-button value="asc">升序</el-radio-button>
          </el-radio-group>
          <el-button type="primary" plain @click="resetFilters">重置</el-button>
        </div>
      </div>

      <div class="batch-bar paper-panel" v-if="selectedIds.length > 0">
        <span>已选 {{ selectedIds.length }} 题</span>
        <div class="batch-actions">
          <el-button type="success" size="small" @click="batchMaster">批量斩题</el-button>
          <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
          <el-button size="small" @click="selectedIds = []">取消选择</el-button>
        </div>
      </div>

      <div v-if="loading" class="paper-panel">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="questions.length === 0" class="paper-panel empty-state">
        <el-empty description="没有符合条件的错题" />
      </div>

      <div v-else class="question-list">
        <div v-for="q in questions" :key="q.question_id" class="paper-panel question-card">
          <div class="question-header">
            <el-checkbox
              :model-value="selectedIds.includes(q.question_id)"
              @change="(val) => toggleSelect(q.question_id, val)"
            />
            <div class="question-meta">
              <el-tag size="small" :type="q.type === 'multiple' ? 'warning' : 'primary'">
                {{ typeLabel(q.type) }}
              </el-tag>
              <span class="bank-name">{{ q.bank_name }}</span>
              <span class="wrong-count">错 {{ q.wrong_count }} 次</span>
              <span v-if="q.last_answer_at" class="answer-time">{{ formatTime(q.last_answer_at) }}</span>
            </div>
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
            <el-button size="small" type="danger" text @click="deleteSingle(q)">
              删除
            </el-button>
          </div>
          <div v-if="q.showExplanation" class="explanation">
            <p><b>正确答案：</b>{{ q.answer.join('、') }}</p>
            <p><b>解析：</b>{{ q.explanation }}</p>
          </div>
        </div>
      </div>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @change="onPageChange"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { quizApi } from '@/api/modules'

const viewMode = ref('banks')
const loading = ref(false)
const loadingBanks = ref(false)
const questions = ref([])
const banks = ref([])
const bankOptions = ref([])
const selectedIds = ref([])

const filters = reactive({
  bank_id: undefined,
  type: undefined,
  min_wrong_count: undefined,
  last_result: undefined,
  keyword: '',
  sort_by: 'last_answer_at',
  order: 'desc',
})

const pagination = reactive({
  page: 1,
  page_size: 10,
  total: 0,
})

const loadBanks = async () => {
  loadingBanks.value = true
  try {
    const res = await quizApi.wrongQuestionBanks()
    banks.value = res.data
    bankOptions.value = res.data.map((b) => ({ bank_id: b.bank_id, bank_name: b.bank_name }))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载题库汇总失败')
  } finally {
    loadingBanks.value = false
  }
}

const loadQuestions = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size,
      sort_by: filters.sort_by,
      order: filters.order,
    }
    if (filters.bank_id !== undefined) params.bank_id = filters.bank_id
    if (filters.type) params.type = filters.type
    if (filters.min_wrong_count !== undefined) params.min_wrong_count = filters.min_wrong_count
    if (filters.last_result) params.last_result = filters.last_result
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()

    const res = await quizApi.wrongQuestions(params)
    questions.value = res.data.items.map((q) => ({ ...q, showExplanation: false }))
    pagination.total = res.data.total
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载错题失败')
  } finally {
    loading.value = false
  }
}

const onViewModeChange = (mode) => {
  selectedIds.value = []
  if (mode === 'banks') {
    loadBanks()
  } else {
    loadQuestions()
  }
}

const enterBank = (bankId) => {
  filters.bank_id = bankId
  viewMode.value = 'all'
  pagination.page = 1
  selectedIds.value = []
  loadQuestions()
}

const onFilterChange = () => {
  pagination.page = 1
  loadQuestions()
}

const onPageChange = () => {
  loadQuestions()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const resetFilters = () => {
  filters.bank_id = undefined
  filters.type = undefined
  filters.min_wrong_count = undefined
  filters.last_result = undefined
  filters.keyword = ''
  filters.sort_by = 'last_answer_at'
  filters.order = 'desc'
  pagination.page = 1
  loadQuestions()
}

const toggleExplanation = (q) => {
  q.showExplanation = !q.showExplanation
}

const toggleSelect = (questionId, checked) => {
  if (checked) {
    if (!selectedIds.value.includes(questionId)) {
      selectedIds.value.push(questionId)
    }
  } else {
    selectedIds.value = selectedIds.value.filter((id) => id !== questionId)
  }
}

const master = async (q) => {
  try {
    await quizApi.master({ question_id: q.question_id, mastered: true })
    ElMessage.success('已斩题')
    removeFromList(q.question_id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '斩题失败')
  }
}

const deleteSingle = async (q) => {
  try {
    await ElMessageBox.confirm('确定要删除这道错题记录吗？删除后不可恢复。', '删除错题', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
      type: 'warning',
    })
    await quizApi.deleteWrongQuestion(q.question_id)
    ElMessage.success('错题已删除')
    removeFromList(q.question_id)
  } catch (error) {
    if (error === 'cancel' || error?.toString().includes('cancel')) return
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

const batchDelete = async () => {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedIds.value.length} 道错题记录吗？删除后不可恢复。`,
      '批量删除错题',
      { confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger', type: 'warning' }
    )
    await quizApi.batchDeleteWrongQuestions({ question_ids: selectedIds.value })
    ElMessage.success(`已删除 ${selectedIds.value.length} 道错题`)
    selectedIds.value = []
    await loadQuestions()
    await loadBanks()
  } catch (error) {
    if (error === 'cancel' || error?.toString().includes('cancel')) return
    ElMessage.error(error.response?.data?.detail || '批量删除失败')
  }
}

const deleteBank = async (bank) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除「${bank.bank_name}」下的所有错题记录吗？删除后不可恢复。`,
      '删除题库错题',
      { confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger', type: 'warning' }
    )
    await quizApi.deleteBankWrongQuestions(bank.bank_id)
    ElMessage.success(`「${bank.bank_name}」的错题已删除`)
    await loadBanks()
    if (viewMode.value === 'all' && filters.bank_id === bank.bank_id) {
      filters.bank_id = undefined
      await loadQuestions()
    }
  } catch (error) {
    if (error === 'cancel' || error?.toString().includes('cancel')) return
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

const batchMaster = async () => {
  if (selectedIds.value.length === 0) return
  try {
    await quizApi.batchMasterWrongQuestions({ question_ids: selectedIds.value, mastered: true })
    ElMessage.success(`已成功斩题 ${selectedIds.value.length} 道`)
    selectedIds.value = []
    await loadQuestions()
    await loadBanks()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '批量斩题失败')
  }
}

const removeFromList = (questionId) => {
  questions.value = questions.value.filter((item) => item.question_id !== questionId)
  selectedIds.value = selectedIds.value.filter((id) => id !== questionId)
  pagination.total = Math.max(0, pagination.total - 1)
}

const formatTime = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const typeLabel = (type) => {
  const map = { single: '单选题', multiple: '多选题', judgment: '判断题' }
  return map[type] || type
}

onMounted(() => {
  loadBanks()
})
</script>

<style scoped>
.view-tabs {
  display: flex;
  justify-content: center;
  margin-bottom: var(--space-6);
}

.bank-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}

.bank-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.bank-card:hover {
  transform: translateY(-2px);
}

.bank-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.bank-card-header h3 {
  margin: 0;
  font-size: var(--text-lg);
  color: var(--gray-900);
  line-height: 1.4;
}

.bank-stats {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
  padding: var(--space-2) var(--space-3);
  background: var(--gray-50);
  border-radius: var(--radius-md);
}

.stat-item strong {
  font-size: var(--text-xl);
  color: var(--gray-900);
}

.stat-item span {
  font-size: var(--text-xs);
  color: var(--gray-500);
}

.bank-time {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--gray-500);
}

.filter-bar {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.filter-row .el-select {
  width: 160px;
}

.filter-row .el-input {
  width: 220px;
}

.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.batch-actions {
  display: flex;
  gap: var(--space-2);
}

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

.question-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.question-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
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

.answer-time {
  color: var(--gray-400);
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

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}

.empty-state {
  text-align: center;
  padding: var(--space-12) 0;
}

@media (max-width: 768px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-row .el-select,
  .filter-row .el-input {
    width: 100% !important;
  }

  .batch-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .bank-grid {
    grid-template-columns: 1fr;
  }
}
</style>
