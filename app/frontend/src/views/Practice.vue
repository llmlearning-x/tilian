<template>
  <div class="page practice-page">
    <header class="page-head compact">
      <div>
        <p class="eyebrow">PRACTICE</p>
        <h1>{{ bank?.name || '刷题练习' }}</h1>
      </div>
      <el-button @click="router.push('/banks')">返回题库中心</el-button>
    </header>

    <!-- 开始面板 -->
    <section v-if="!sessionId && !resumingSession" class="paper-panel start-panel">
      <h2>选择练习方式</h2>
      <p>题目共 {{ bank?.question_count || 0 }} 道。每题提交后可查看解析、个人历史正确率和全网正确率。</p>
      <el-radio-group v-model="mode">
        <el-radio value="sequential">顺序练习</el-radio>
        <el-radio value="random">随机练习</el-radio>
      </el-radio-group>
      <div>
        <el-button type="primary" size="large" :loading="busy" @click="start">开始练习</el-button>
      </div>
    </section>

    <!-- 断点续练提示 -->
    <section v-if="unfinishedSessions.length > 0 && !sessionId && !resumingSession" class="paper-panel resume-panel">
      <h3>你有未完成的练习</h3>
      <div v-for="s in unfinishedSessions" :key="s.session_id" class="resume-item">
        <span>{{ s.bank_name }} · 进度 {{ s.current_index + 1 }} / {{ s.total_count }}</span>
        <div>
          <el-button type="primary" size="small" @click="resume(s.session_id)">继续练习</el-button>
          <el-button size="small" @click="abandon(s.session_id)">放弃</el-button>
        </div>
      </div>
    </section>

    <!-- 答题面板 -->
    <section v-else-if="current" class="question-stage">
      <aside class="question-rail">
        <div>
          <b>{{ current.seq + 1 }}</b>
          <span>/ {{ total }}</span>
        </div>
        <el-progress :percentage="Math.round(((current.seq + 1) / total) * 100)" :show-text="false" />
      </aside>
      <article class="question-paper">
        <div class="question-head">
          <span class="question-type">{{ typeLabel(current.type) }}</span>
          <el-button v-if="!mastered" size="small" type="success" plain @click="master(true)">
            ✓ 斩题
          </el-button>
          <el-tag v-else type="success" size="small">已斩题</el-tag>
        </div>
        <h2>{{ current.stem }}</h2>
        <el-radio-group
          v-if="current.type === 'single' || current.type === 'judgment'"
          v-model="singleAnswer"
          :disabled="Boolean(feedback)"
          class="option-list"
        >
          <el-radio v-for="option in current.options" :key="option.label" :value="option.label" border>
            <b>{{ option.label }}</b>{{ option.content }}
          </el-radio>
        </el-radio-group>
        <el-checkbox-group
          v-else
          v-model="multipleAnswer"
          :disabled="Boolean(feedback)"
          class="option-list"
        >
          <el-checkbox v-for="option in current.options" :key="option.label" :value="option.label" border>
            <b>{{ option.label }}</b>{{ option.content }}
          </el-checkbox>
        </el-checkbox-group>

        <div v-if="feedback" class="feedback" :class="feedback.is_correct ? 'correct' : 'wrong'">
          <h3>{{ feedback.is_correct ? '回答正确' : '回答错误' }}</h3>
          <p><b>正确答案：</b>{{ feedback.correct_answer.join('、') }}</p>
          <p class="explanation"><b>解析：</b>{{ feedback.explanation }}</p>
          <div class="accuracy-grid">
            <div>
              <span>我的历史正确率</span>
              <strong>{{ feedback.personal_accuracy.rate }}%</strong>
              <small>{{ feedback.personal_accuracy.correct }}/{{ feedback.personal_accuracy.attempts }} 次</small>
            </div>
            <div>
              <span>全网正确率</span>
              <strong>{{ feedback.global_accuracy.rate }}%</strong>
              <small>{{ feedback.global_accuracy.correct }}/{{ feedback.global_accuracy.attempts }} 次</small>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <el-button v-if="!feedback" type="primary" size="large" :loading="busy" @click="submit">
            提交答案
          </el-button>
          <el-button v-else type="primary" size="large" @click="next">
            {{ feedback.can_continue ? '下一题' : '查看结果' }}
          </el-button>
        </div>
      </article>
    </section>

    <!-- 结果面板 -->
    <section v-else-if="result" class="paper-panel result-panel">
      <p class="eyebrow">PRACTICE RECORD</p>
      <h2>练习记录</h2>
      <strong>{{ result.accuracy }}%</strong>
      <p>答对 {{ result.correct_count }} 题，共 {{ result.total_count }} 题</p>
      <div>
        <el-button size="large" @click="restart">再练一次</el-button>
        <el-button type="primary" size="large" @click="router.push('/banks')">返回题库中心</el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bankApi, quizApi } from '@/api/modules'

const route = useRoute()
const router = useRouter()
const bankId = Number(route.params.bankId)

const bank = ref(null)
const mode = ref('sequential')
const busy = ref(false)
const sessionId = ref(null)
const resumingSession = ref(false)
const total = ref(0)
const current = ref(null)
const feedback = ref(null)
const result = ref(null)
const singleAnswer = ref('')
const multipleAnswer = ref([])
const unfinishedSessions = ref([])
const mastered = ref(false)

const storageKey = `practice_session_${bankId}`

const load = async () => {
  try {
    bank.value = (await bankApi.get(bankId)).data
    await loadUnfinishedSessions()
    // 如果 localStorage 中保存了当前题库的 session_id，尝试恢复
    const savedSessionId = localStorage.getItem(storageKey)
    if (savedSessionId && !sessionId.value) {
      try {
        const res = await quizApi.resume(Number(savedSessionId))
        sessionId.value = res.data.session_id
        total.value = res.data.total_count
        current.value = res.data.question
        await checkMastered(current.value.id)
        unfinishedSessions.value = []
      } catch {
        localStorage.removeItem(storageKey)
      }
    }
  } catch {
    ElMessage.error('题库不存在')
    router.push('/banks')
  }
}

const loadUnfinishedSessions = async () => {
  try {
    unfinishedSessions.value = (await quizApi.unfinishedSessions(bankId)).data
  } catch {
    unfinishedSessions.value = []
  }
}

const checkMastered = async (questionId) => {
  try {
    const list = (await quizApi.masteredQuestions(bankId)).data
    mastered.value = list.some((item) => item.question_id === questionId)
  } catch {
    mastered.value = false
  }
}

const start = async () => {
  busy.value = true
  try {
    const res = await quizApi.start({
      bank_id: bankId,
      mode: mode.value
    })
    sessionId.value = res.data.session_id
    total.value = res.data.total_count
    current.value = res.data.first_question
    feedback.value = null
    singleAnswer.value = ''
    multipleAnswer.value = []
    localStorage.setItem(storageKey, sessionId.value)
    await checkMastered(current.value.id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '无法开始练习')
  } finally {
    busy.value = false
  }
}

const resume = async (id) => {
  busy.value = true
  resumingSession.value = true
  try {
    const res = await quizApi.resume(id)
    sessionId.value = res.data.session_id
    total.value = res.data.total_count
    current.value = res.data.question
    feedback.value = null
    singleAnswer.value = ''
    multipleAnswer.value = []
    localStorage.setItem(storageKey, sessionId.value)
    await checkMastered(current.value.id)
    unfinishedSessions.value = []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '恢复练习失败')
  } finally {
    busy.value = false
    resumingSession.value = false
  }
}

const abandon = async (id) => {
  try {
    await ElMessageBox.confirm('放弃后进度将丢失，确定要继续吗？', '提示', { type: 'warning' })
    // 服务端没有单独放弃接口，直接删除 localStorage 并刷新列表
    if (Number(localStorage.getItem(storageKey)) === id) {
      localStorage.removeItem(storageKey)
    }
    unfinishedSessions.value = unfinishedSessions.value.filter((s) => s.session_id !== id)
  } catch {
    // 取消
  }
}

const submit = async () => {
  const answer =
    current.value.type === 'multiple'
      ? multipleAnswer.value
      : singleAnswer.value
        ? [singleAnswer.value]
        : []
  if (!answer.length) return ElMessage.warning('请先选择答案')
  busy.value = true
  try {
    feedback.value = (
      await quizApi.submit({
        session_id: sessionId.value,
        question_id: current.value.id,
        answer
      })
    ).data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '提交失败')
  } finally {
    busy.value = false
  }
}

const next = async () => {
  if (!feedback.value.can_continue) {
    result.value = (await quizApi.result(sessionId.value)).data
    current.value = null
    localStorage.removeItem(storageKey)
    return
  }
  const res = await quizApi.next(sessionId.value)
  current.value = res.data.question
  feedback.value = null
  singleAnswer.value = ''
  multipleAnswer.value = []
  await checkMastered(current.value.id)
}

const master = async (flag) => {
  if (!current.value) return
  try {
    await quizApi.master({ question_id: current.value.id, mastered: flag })
    mastered.value = flag
    ElMessage.success(flag ? '已斩题' : '已取消斩题')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const restart = () => {
  sessionId.value = null
  current.value = null
  feedback.value = null
  result.value = null
  localStorage.removeItem(storageKey)
  loadUnfinishedSessions()
}

const typeLabel = (type) => {
  const map = { single: '单选题', multiple: '多选题', judgment: '判断题' }
  return map[type] || type
}

onMounted(load)
</script>

<style scoped>
.resume-panel {
  margin-top: var(--space-5);
}
.resume-panel h3 {
  margin: 0 0 var(--space-3);
  font-size: var(--text-lg);
}
.resume-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--gray-100);
}
.resume-item:last-child {
  border-bottom: none;
}
.question-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
</style>
