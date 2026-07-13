<template>
  <div class="page narrow-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">DOCUMENT TO BANK</p>
        <h1>文档炼题</h1>
        <p>上传学习资料，AI 自动提取知识点并生成练习题。生成后先预览，确认后再保存到我的题库。</p>
      </div>
    </header>

    <el-steps :active="step" finish-status="success" simple>
      <el-step title="上传文档" />
      <el-step title="设置题量" />
      <el-step title="生成预览" />
    </el-steps>

    <section v-if="step === 0" class="paper-panel">
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf,.docx,.txt,.md,.markdown"
        :on-change="chooseFile"
        :on-remove="() => (file = null)"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div>拖入学习文档，或点击选择</div>
        <template #tip>
          <p>PDF、DOCX、TXT、Markdown，最大 10 MB</p>
        </template>
      </el-upload>
      <div class="form-actions">
        <el-button type="primary" :loading="busy" :disabled="!file" @click="upload">
          上传并继续
        </el-button>
      </div>
    </section>

    <section v-else-if="step === 1" class="paper-panel">
      <el-form label-position="top">
        <el-form-item label="题库名称">
          <el-input v-model="form.bank_name" maxlength="100" show-word-limit placeholder="给生成的题库起个名字" />
        </el-form-item>
        <el-form-item label="题目数量（合计不超过 20 题）">
          <div class="count-row">
            <label>
              <span>单选题</span>
              <el-input-number v-model="form.single_count" :min="0" :max="20" />
            </label>
            <label>
              <span>多选题</span>
              <el-input-number v-model="form.multiple_count" :min="0" :max="20" />
            </label>
          </div>
        </el-form-item>
        <el-form-item label="难度">
          <el-radio-group v-model="form.difficulty">
            <el-radio-button value="easy">基础</el-radio-button>
            <el-radio-button value="medium">中等</el-radio-button>
            <el-radio-button value="hard">较难</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <el-alert v-if="job?.status === 'failed'" type="error" :title="job.error_message" show-icon :closable="false" />
      <div class="form-actions">
        <el-button @click="step = 0">上一步</el-button>
        <el-button v-if="job?.status === 'failed'" :loading="busy" @click="retry">重试</el-button>
        <el-button type="primary" :loading="busy" @click="generate">
          {{ busy ? '正在生成…' : '生成题库' }}
        </el-button>
      </div>
    </section>

    <section v-else class="preview-list">
      <div class="preview-head">
        <div>
          <h2>生成预览</h2>
          <p>共 {{ job.questions.length }} 题，确认后才会保存到“我的题库”。</p>
        </div>
        <el-button type="primary" :loading="busy" @click="confirm">确认并保存题库</el-button>
      </div>
      <article v-for="(question, index) in job.questions" :key="index" class="question-editor">
        <div class="question-index">{{ String(index + 1).padStart(2, '0') }} · {{ typeLabel(question.type) }}</div>
        <el-input v-model="question.stem" type="textarea" autosize />
        <div v-for="option in question.options" :key="option.label" class="option-edit">
          <b>{{ option.label }}</b>
          <el-input v-model="option.content" />
        </div>
        <el-form label-position="top">
          <el-form-item label="答案（选项标签）">
            <el-select v-model="question.answer" multiple>
              <el-option v-for="option in question.options" :key="option.label" :label="option.label" :value="option.label" />
            </el-select>
          </el-form-item>
          <el-form-item label="解析">
            <el-input v-model="question.explanation" type="textarea" autosize />
          </el-form-item>
        </el-form>
        <div class="editor-actions">
          <el-button @click="saveQuestion(index, question)">保存修改</el-button>
          <el-button text type="danger" @click="deleteQuestion(index)">删除本题</el-button>
        </div>
      </article>
      <div class="form-actions" style="margin-top: var(--space-8)">
        <el-button type="primary" :loading="busy" @click="confirm">确认并保存题库</el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { documentApi, generationApi } from '@/api/modules'

const router = useRouter()
const step = ref(0)
const file = ref(null)
const documentId = ref(null)
const job = ref(null)
const busy = ref(false)
let timer = null

const form = reactive({
  bank_name: '',
  single_count: 5,
  multiple_count: 0,
  difficulty: 'medium'
})

const chooseFile = (uploadFile) => {
  file.value = uploadFile.raw
  if (!form.bank_name) form.bank_name = uploadFile.name.replace(/\.[^.]+$/, '')
}

const upload = async () => {
  busy.value = true
  try {
    const res = await documentApi.upload(file.value)
    documentId.value = res.data.id
    step.value = 1
    ElMessage.success('文档解析成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '文档上传失败')
  } finally {
    busy.value = false
  }
}

const poll = async () => {
  const res = await generationApi.get(job.value.id)
  job.value = res.data
  if (job.value.status === 'ready') {
    busy.value = false
    step.value = 2
    clearInterval(timer)
  }
  if (job.value.status === 'failed') {
    busy.value = false
    clearInterval(timer)
  }
}

const generate = async () => {
  const total = form.single_count + form.multiple_count
  if (!form.bank_name.trim()) return ElMessage.warning('请输入题库名称')
  if (total < 1 || total > 20) return ElMessage.warning('题目总数必须为 1 到 20 题')
  busy.value = true
  try {
    const res = await generationApi.create({ ...form, document_id: documentId.value })
    job.value = res.data
    timer = setInterval(poll, 1200)
    await poll()
  } catch (error) {
    busy.value = false
    ElMessage.error(error.response?.data?.detail || '创建生成任务失败')
  }
}

const retry = async () => {
  busy.value = true
  await generationApi.retry(job.value.id)
  timer = setInterval(poll, 1200)
  await poll()
}

const saveQuestion = async (index, question) => {
  const res = await generationApi.updateQuestion(job.value.id, index, question)
  job.value = res.data
  ElMessage.success('修改已保存')
}

const deleteQuestion = async (index) => {
  const res = await generationApi.removeQuestion(job.value.id, index)
  job.value = res.data
}

const confirm = async () => {
  busy.value = true
  try {
    const res = await generationApi.confirm(job.value.id)
    ElMessage.success('已保存到我的题库')
    router.push(`/practice/${res.data.bank_id}`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '题库保存失败')
  } finally {
    busy.value = false
  }
}

const typeLabel = (type) => {
  const map = { single: '单选题', multiple: '多选题', judgment: '判断题' }
  return map[type] || type
}

onBeforeUnmount(() => clearInterval(timer))
</script>
