import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Landing', component: () => import('@/views/Landing.vue') },
  {
    path: '/banks',
    name: 'Banks',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true, scope: 'all' }
  },
  {
    path: '/platform',
    name: 'PlatformBanks',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true, scope: 'platform' }
  },
  {
    path: '/my-banks',
    name: 'MyBanks',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true, scope: 'mine' }
  },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
  { path: '/generate', name: 'Generate', component: () => import('@/views/Generate.vue'), meta: { requiresAuth: true } },
  { path: '/practice/:bankId?', name: 'Practice', component: () => import('@/views/Practice.vue'), meta: { requiresAuth: true } },
  { path: '/records', name: 'Records', component: () => import('@/views/Records.vue'), meta: { requiresAuth: true } },
  { path: '/wrong-questions', name: 'WrongQuestions', component: () => import('@/views/WrongQuestions.vue'), meta: { requiresAuth: true } },
  { path: '/admin', name: 'Admin', component: () => import('@/views/Admin.vue'), meta: { requiresAuth: true, admin: true } },
  { path: '/knowledge', redirect: '/generate' },
  { path: '/questions', redirect: '/generate' }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')
  if (to.meta.requiresAuth && !token) return { name: 'Login' }
  if (to.meta.admin && user?.role !== 'admin') return { name: 'Banks' }
  if (to.path === '/login' && token) return { name: 'Banks' }
})

export default router
