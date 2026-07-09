<template>
  <div class="page narrow-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">ADMINISTRATION</p>
        <h1>平台题库管理</h1>
        <p>维护学习者可直接使用的基础题库，支持标准 JSON 导入与 AI Agent 自动整理。</p>
      </div>
    </header>

    <!-- 标准 JSON 导入 -->
    <section class="paper-panel">
      <h2 class="panel-title">标准 JSON 导入</h2>
      <p class="panel-desc">使用标准 JSON 文件维护基础题库。系统会先全量校验，再一次性导入。</p>
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".json"
        :on-change="(item) => (jsonFile = item.raw)"
        :on-remove="() => (jsonFile = null)"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div>选择 UTF-8 JSON 题库文件</div>
        <template #tip>
          <p>最大 2 MB；任一题不合法时不会写入任何数据。</p>
        </template>
      </el-upload>
      <el-alert v-if="validation" type="success" :title="`${validation.name}：${validation.question_count} 题，校验通过`" show-icon :closable="false" />
      <div class="form-actions">
        <el-button :disabled="!jsonFile" :loading="busy" @click="validateJson">校验文件</el-button>
        <el-button type="primary" :disabled="!validation" :loading="busy" @click="importBank">确认导入</el-button>
      </div>
    </section>

    <!-- AI Agent 自动整理 -->
    <section class="paper-panel">
      <h2 class="panel-title">AI Agent 自动整理</h2>
      <p class="panel-desc">上传 PDF、Word、TXT、Markdown 甚至不规范的 JSON，由 DeepAgents + Kimi 自动整理为标准题库。</p>
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf,.docx,.txt,.md,.json"
        :on-change="(item) => (agentFile = item.raw)"
        :on-remove="() => { agentFile = null; resetAgent() }"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div>选择任意格式文档</div>
        <template #tip>
          <p>支持 PDF / DOCX / TXT / MD / JSON，最大 10 MB。</p>
        </template>
      </el-upload>

      <div class="form-actions">
        <el-button type="primary" :disabled="!agentFile || agentBusy" :loading="agentBusy" @click="startAgentStream">
          <el-icon><Cpu /></el-icon> 启动 Agent 整理
        </el-button>
        <el-button v-if="agentData" type="success" :disabled="!agentData.valid" @click="importAgentResult">
          导入整理结果
        </el-button>
      </div>

      <!-- Agent 执行过程 -->
      <div v-if="agentEvents.length > 0" class="agent-stream">
        <h3 class="stream-title">Agent 思考与执行过程</h3>
        <div class="stream-list">
          <div
            v-for="(event, index) in agentEvents"
            :key="index"
            class="stream-item"
            :class="event.type"
          >
            <div class="stream-header">
              <span class="stream-badge">{{ typeLabel(event.type) }}</span>
              <span v-if="event.tool_name" class="stream-tool">{{ event.tool_name }}</span>
            </div>
            <pre v-if="event.content" class="stream-content">{{ event.content }}</pre>
            <pre v-if="event.tool_args" class="stream-args">输入：{{ formatJson(event.tool_args) }}</pre>
            <pre v-if="event.tool_result" class="stream-result">输出：{{ event.tool_result }}</pre>
            <div v-if="event.todos" class="stream-todos">
              <div v-for="todo in event.todos" :key="todo.content" class="stream-todo" :class="todo.status">
                {{ statusIcon(todo.status) }} {{ todo.content }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <el-alert v-if="agentData" :type="agentData.valid ? 'success' : 'error'" :closable="false" class="agent-result">
        <template #title>
          <span v-if="agentData.valid">
            整理完成：{{ agentData.data?.name }}，共 {{ agentData.data?.questions?.length || 0 }} 题
          </span>
          <span v-else>整理失败：{{ agentData.validation }}</span>
        </template>
      </el-alert>
    </section>

    <!-- 平台题库管理 -->
    <section class="paper-panel">
      <h2 class="panel-title">题库列表</h2>
      <p class="panel-desc">管理平台题库的上架、下架与删除。</p>
      <div class="bank-filter">
        <el-radio-group v-model="bankFilter" size="small" @change="loadBanks">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="ready">已上架</el-radio-button>
          <el-radio-button label="draft">已下架</el-radio-button>
        </el-radio-group>
        <el-button size="small" :loading="bankLoading" @click="loadBanks">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
      <div class="table-scroll">
        <el-table v-loading="bankLoading" :data="banks" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="题库名称" min-width="140" />
          <el-table-column prop="question_count" label="题目数" width="80" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ready' ? 'success' : 'info'">
                {{ row.status === 'ready' ? '已上架' : '已下架' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="160" class-name="hidden-xs">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button
                size="small"
                :type="row.status === 'ready' ? 'warning' : 'primary'"
                @click="toggleBankStatus(row)"
              >
                {{ row.status === 'ready' ? '下架' : '上架' }}
              </el-button>
              <el-button size="small" type="danger" @click="deleteBank(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Cpu, Refresh } from '@element-plus/icons-vue'
import { adminApi } from '@/api/modules'

const jsonFile = ref(null)
const validation = ref(null)
const busy = ref(false)

const agentFile = ref(null)
const agentBusy = ref(false)
const agentEvents = ref([])
const agentData = ref(null)

const banks = ref([])
const bankLoading = ref(false)
const bankFilter = ref('all')

const loadBanks = async () => {
  bankLoading.value = true
  try {
    banks.value = (await adminApi.listBanks(bankFilter.value)).data
  } catch (error) {
    ElMessage.error(detail(error))
  } finally {
    bankLoading.value = false
  }
}

const toggleBankStatus = async (row) => {
  const newStatus = row.status === 'ready' ? 'draft' : 'ready'
  try {
    await adminApi.updateBankStatus(row.id, newStatus)
    ElMessage.success(newStatus === 'ready' ? '已上架' : '已下架')
    loadBanks()
  } catch (error) {
    ElMessage.error(detail(error))
  }
}

const deleteBank = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除题库《${row.name}》吗？`, '提示', { type: 'warning' })
    await adminApi.deleteBank(row.id)
    ElMessage.success('已删除')
    loadBanks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(detail(error))
    }
  }
}

const formatDate = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(loadBanks)

const detail = (error) =>
  typeof error.response?.data?.detail === 'string'
    ? error.response.data.detail
    : error.response?.data?.detail?.message || '操作失败'

const validateJson = async () => {
  busy.value = true
  validation.value = null
  try {
    validation.value = (await adminApi.validate(jsonFile.value)).data
  } catch (error) {
    ElMessage.error(detail(error))
  } finally {
    busy.value = false
  }
}

const importBank = async () => {
  busy.value = true
  try {
    const res = await adminApi.importBank(jsonFile.value)
    ElMessage.success(`已导入 ${res.data.question_count} 题`)
    validation.value = null
    jsonFile.value = null
  } catch (error) {
    ElMessage.error(detail(error))
  } finally {
    busy.value = false
  }
}

const resetAgent = () => {
  agentEvents.value = []
  agentData.value = null
}

const typeLabel = (type) => {
  const map = {
    start: '开始',
    thought: '思考',
    tool_call: '调用工具',
    tool_result: '工具返回',
    todo: '任务列表',
    final: '完成',
    heartbeat: '执行中',
    raw: '原始事件',
  }
  return map[type] || type
}

const statusIcon = (status) => {
  if (status === 'completed') return '✅'
  if (status === 'in_progress') return '🔄'
  return '⏳'
}

const formatJson = (obj) => JSON.stringify(obj, null, 2)

const startAgentStream = () => {
  if (!agentFile.value) return
  resetAgent()
  agentBusy.value = true

  const token = localStorage.getItem('access_token')
  const formData = new FormData()
  formData.append('file', agentFile.value)

  fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'}/api/admin/bank-organizer/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error('Agent 启动失败')
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const read = () => {
        reader.read().then(({ done, value }) => {
          if (done) {
            agentBusy.value = false
            return
          }
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''

          lines.forEach((line) => {
            if (!line.trim().startsWith('data:')) return
            const data = line.trim().slice(5).trim()
            if (data === '[DONE]') {
              agentBusy.value = false
              return
            }
            try {
              const event = JSON.parse(data)
              if (event.type === 'final') {
                agentData.value = event
                if (event.valid) {
                  ElMessage.success(`Agent 整理完成：${event.data?.name}，共 ${event.data?.questions?.length || 0} 题`)
                } else {
                  ElMessage.error(event.validation)
                }
              } else {
                agentEvents.value.push(event)
              }
            } catch (e) {
              console.warn('无法解析 SSE 事件:', data)
            }
          })

          read()
        }).catch((err) => {
          agentBusy.value = false
          ElMessage.error(`Agent 流读取失败：${err.message}`)
        })
      }

      read()
    })
    .catch((err) => {
      agentBusy.value = false
      ElMessage.error(err.message)
    })
}

const importAgentResult = async () => {
  if (!agentData.value?.data) return
  busy.value = true
  try {
    // 将整理结果导出为 Blob，复用 adminApi.importBank
    const blob = new Blob([JSON.stringify(agentData.value.data)], { type: 'application/json' })
    const file = new File([blob], `${agentData.value.data.name || 'agent-bank'}.json`, { type: 'application/json' })
    const res = await adminApi.importBank(file)
    ElMessage.success(`已导入 ${res.data.question_count} 题`)
    agentData.value = null
    agentFile.value = null
    resetAgent()
  } catch (error) {
    ElMessage.error(detail(error))
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.panel-title {
  font-size: var(--text-xl);
  font-weight: 700;
  margin: 0 0 var(--space-2);
}
.panel-desc {
  color: var(--gray-600);
  margin: 0 0 var(--space-5);
}
.agent-stream {
  margin-top: var(--space-6);
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-lg);
  background: var(--gray-50);
  padding: var(--space-4);
}
.stream-title {
  font-size: var(--text-lg);
  font-weight: 600;
  margin: 0 0 var(--space-4);
}
.stream-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: 600px;
  overflow-y: auto;
}
.stream-item {
  border-radius: var(--radius-md);
  background: #fff;
  padding: var(--space-3);
  border-left: 4px solid var(--gray-300);
}
.stream-item.thought { border-left-color: var(--brand-500); }
.stream-item.tool_call { border-left-color: var(--violet-500); }
.stream-item.tool_result { border-left-color: var(--cyan-500); }
.stream-item.todo { border-left-color: var(--warning); }
.stream-item.final { border-left-color: var(--success); }
.stream-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.stream-badge {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-700);
}
.stream-tool {
  font-size: var(--text-xs);
  color: var(--brand-600);
  font-family: monospace;
}
.stream-content,
.stream-args,
.stream-result {
  margin: var(--space-2) 0 0;
  padding: var(--space-2);
  background: var(--gray-50);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}
.stream-todos {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-top: var(--space-2);
}
.stream-todo {
  font-size: var(--text-xs);
  color: var(--gray-700);
}
.agent-result {
  margin-top: var(--space-4);
}
.bank-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}
</style>
