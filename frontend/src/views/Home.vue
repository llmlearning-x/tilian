<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">{{ eyebrowText }}</p>
        <h1>{{ titleText }}</h1>
        <p>{{ descText }}</p>
      </div>
      <el-button type="primary" size="large" @click="router.push('/generate')">
        <el-icon><Upload /></el-icon>文档炼题
      </el-button>
    </header>

    <section v-if="showPlatform">
      <div class="section-title">
        <h2>平台题库</h2>
        <span>{{ platform.length }} 个题库</span>
      </div>
      <div v-if="platform.length" class="bank-grid">
        <article v-for="bank in platform" :key="bank.id" class="bank-sheet">
          <span class="bank-kind">平台题库</span>
          <h3>{{ bank.name }}</h3>
          <p>{{ bank.description || '暂无说明' }}</p>
          <div class="bank-meta">
            <span>{{ bank.question_count }} 题</span>
            <span>{{ typeText(bank.question_types) }}</span>
          </div>
          <el-button type="primary" :disabled="!bank.question_count" @click="practice(bank.id)">
            开始练习
          </el-button>
        </article>
      </div>
      <el-empty v-else-if="!loading" description="暂无平台题库" />
    </section>

    <section v-if="showMine">
      <div class="section-title">
        <h2>我的题库</h2>
        <span>{{ mine.length }} 个题库</span>
      </div>
      <div v-if="mine.length" class="bank-grid mine-grid">
        <article v-for="bank in mine" :key="bank.id" class="bank-sheet personal">
          <span class="bank-kind">我的题库</span>
          <h3>{{ bank.name }}</h3>
          <p>{{ bank.description || '由学习文档生成' }}</p>
          <div class="bank-meta">
            <span>{{ bank.question_count }} 题</span>
            <span>{{ typeText(bank.question_types) }}</span>
          </div>
          <div class="bank-actions">
            <el-button type="primary" :disabled="!bank.question_count" @click="practice(bank.id)">
              开始练习
            </el-button>
            <div class="bank-actions-secondary">
              <el-button @click="manage(bank)">管理</el-button>
              <el-button text type="danger" @click="removeBank(bank)">删除</el-button>
            </div>
          </div>
        </article>
      </div>
      <el-empty v-else-if="!loading" description="还没有我的题库">
        <el-button type="primary" @click="router.push('/generate')">
          <el-icon><Upload /></el-icon>去文档炼题
        </el-button>
      </el-empty>
    </section>

    <el-dialog v-model="managerOpen" title="管理我的题库" width="min(820px, 94vw)">
      <el-form v-if="editingBank" label-position="top">
        <el-form-item label="题库名称">
          <el-input v-model="editingBank.name" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="题库说明">
          <el-input v-model="editingBank.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-button type="primary" @click="saveBank">保存题库信息</el-button>
      </el-form>
      <el-divider>题目</el-divider>
      <article v-for="question in editingQuestions" :key="question.id" class="question-editor">
        <div class="question-index">{{ question.type === 'single' ? '单选题' : '多选题' }}</div>
        <el-input v-model="question.stem" type="textarea" autosize />
        <div v-for="option in question.options" :key="option.label" class="option-edit">
          <b>{{ option.label }}</b>
          <el-input v-model="option.content" />
        </div>
        <el-form label-position="top">
          <el-form-item label="答案">
            <el-select v-model="question.answer" multiple>
              <el-option v-for="option in question.options" :key="option.label" :label="option.label" :value="option.label" />
            </el-select>
          </el-form-item>
          <el-form-item label="解析">
            <el-input v-model="question.explanation" type="textarea" autosize />
          </el-form-item>
        </el-form>
        <div class="editor-actions">
          <el-button @click="saveQuestion(question)">保存题目</el-button>
          <el-button text type="danger" @click="removeQuestion(question)">删除题目</el-button>
        </div>
      </article>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { bankApi, questionApi } from '@/api/modules'

const route = useRoute()
const router = useRouter()
const platform = ref([])
const mine = ref([])
const loading = ref(true)
const managerOpen = ref(false)
const editingBank = ref(null)
const editingQuestions = ref([])

const scope = computed(() => route.meta?.scope || 'all')
const showPlatform = computed(() => scope.value === 'all' || scope.value === 'platform')
const showMine = computed(() => scope.value === 'all' || scope.value === 'mine')

const eyebrowText = computed(() => {
  if (scope.value === 'platform') return 'PLATFORM BANKS'
  if (scope.value === 'mine') return 'MY BANKS'
  return 'TILIAN BANKS'
})

const titleText = computed(() => {
  if (scope.value === 'platform') return '平台题库'
  if (scope.value === 'mine') return '我的题库'
  return '题库中心'
})

const descText = computed(() => {
  if (scope.value === 'platform') return '直接使用平台精选题库开始练习。'
  if (scope.value === 'mine') return '管理由学习文档生成的专属题库。'
  return '在平台题库直接开始练习，或进入文档炼题上传资料生成专属题库。'
})

const load = async () => {
  loading.value = true
  try {
    const [platformRes, mineRes] = await Promise.all([
      bankApi.list('platform'),
      bankApi.list('mine')
    ])
    platform.value = platformRes.data
    mine.value = mineRes.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '题库加载失败')
  } finally {
    loading.value = false
  }
}

const typeText = (types) =>
  (types || []).map((type) => (type === 'single' ? '单选' : '多选')).join(' · ') || '暂无题目'

const practice = (id) => router.push(`/practice/${id}`)

const manage = async (bank) => {
  editingBank.value = { ...bank }
  editingQuestions.value = (await bankApi.questions(bank.id)).data
  managerOpen.value = true
}

const saveBank = async () => {
  await bankApi.update(editingBank.value.id, {
    name: editingBank.value.name,
    description: editingBank.value.description
  })
  ElMessage.success('题库信息已保存')
  load()
}

const saveQuestion = async (question) => {
  const { type, stem, options, answer, explanation, difficulty } = question
  await questionApi.update(question.id, { type, stem, options, answer, explanation, difficulty })
  ElMessage.success('题目已保存')
}

const removeQuestion = async (question) => {
  await questionApi.remove(question.id)
  editingQuestions.value = editingQuestions.value.filter((item) => item.id !== question.id)
  ElMessage.success('题目已删除')
  load()
}

const removeBank = async (bank) => {
  await ElMessageBox.confirm(`确定删除“${bank.name}”吗？`, '删除题库', { type: 'warning' })
  await bankApi.remove(bank.id)
  ElMessage.success('题库已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.bank-actions-secondary {
  display: flex;
  gap: var(--space-3);
}

@media (max-width: 768px) {
  .bank-actions {
    flex-direction: column;
  }

  .bank-actions-secondary {
    justify-content: flex-end;
  }
}
</style>
