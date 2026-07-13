import api from './index'

export const authApi = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  getProfile: () => api.get('/auth/profile')
}

export const bankApi = {
  list: (scope) => api.get('/banks/', { params: { scope } }),
  get: (id) => api.get(`/banks/${id}`),
  questions: (id) => api.get(`/banks/${id}/questions`),
  update: (id, data) => api.patch(`/banks/${id}`, data),
  remove: (id) => api.delete(`/banks/${id}`)
}

export const questionApi = {
  update: (id, data) => api.patch(`/questions/${id}`, data),
  remove: (id) => api.delete(`/questions/${id}`)
}

export const documentApi = {
  upload(file) {
    const form = new FormData()
    form.append('file', file)
    return api.post('/documents', form, { timeout: 30000 })
  }
}

export const generationApi = {
  create: (data) => api.post('/generation-jobs', data, { timeout: 60000 }),
  get: (id) => api.get(`/generation-jobs/${id}`),
  updateQuestion: (jobId, index, data) => api.patch(`/generation-jobs/${jobId}/questions/${index}`, data),
  removeQuestion: (jobId, index) => api.delete(`/generation-jobs/${jobId}/questions/${index}`),
  confirm: (id) => api.post(`/generation-jobs/${id}/confirm`),
  retry: (id) => api.post(`/generation-jobs/${id}/retry`, null, { timeout: 60000 })
}

export const quizApi = {
  start: (data) => api.post('/quiz/start', data),
  next: (id) => api.get(`/quiz/next/${id}`),
  submit: (data) => api.post('/quiz/submit', data),
  result: (id) => api.get(`/quiz/result/${id}`),
  sessions: () => api.get('/quiz/sessions'),
  deleteSession: (id) => api.delete(`/quiz/sessions/${id}`),
  unfinishedSessions: (bankId) => api.get('/quiz/sessions/unfinished', { params: bankId ? { bank_id: bankId } : {} }),
  resume: (id) => api.get(`/quiz/resume/${id}`),
  wrongQuestions: (params) => api.get('/quiz/wrong-questions', { params }),
  wrongQuestionBanks: () => api.get('/quiz/wrong-questions/banks'),
  batchMasterWrongQuestions: (data) => api.post('/quiz/wrong-questions/batch-master', data),
  batchClearWrongQuestions: (data) => api.post('/quiz/wrong-questions/batch-clear', data),
  deleteWrongQuestion: (id) => api.delete(`/quiz/wrong-questions/${id}`),
  batchDeleteWrongQuestions: (data) => api.post('/quiz/wrong-questions/batch-delete', data),
  deleteBankWrongQuestions: (bankId) => api.delete(`/quiz/wrong-questions/banks/${bankId}`),
  master: (data) => api.post('/quiz/master', data),
  masteredQuestions: (bankId) => api.get('/quiz/mastered-questions', { params: bankId ? { bank_id: bankId } : {} })
}

export const adminApi = {
  validate(file) {
    const form = new FormData()
    form.append('file', file)
    return api.post('/admin/bank-imports/validate', form)
  },
  importBank(file) {
    const form = new FormData()
    form.append('file', file)
    return api.post('/admin/bank-imports', form)
  },
  listBanks: (status = 'all') => api.get('/admin/banks', { params: { status } }),
  updateBankStatus: (id, status) => api.patch(`/admin/banks/${id}/status`, { status }),
  deleteBank: (id) => api.delete(`/admin/banks/${id}`),
  listInviteCodes: (status = 'all') => api.get('/admin/invite-codes', { params: { status } }),
  createInviteCodes: (data) => api.post('/admin/invite-codes', data),
  deleteInviteCode: (id) => api.delete(`/admin/invite-codes/${id}`)
}
