<template>
  <div class="shell">
    <!-- 顶部门户导航 -->
    <header v-if="route.path !== '/login'" class="portal-header">
      <div class="header-inner">
        <button class="brand" @click="navigate('/')">
          <span class="brand-mark">TILIAN</span>
          <span class="brand-text">题炼</span>
        </button>

        <nav class="header-nav" :class="{ open: menuOpen }">
          <button
            :class="{ active: route.path === '/platform' }"
            @click="navigate('/platform')"
          >
            平台题库
          </button>
          <button
            :class="{ active: route.path.startsWith('/generate') }"
            @click="navigate('/generate')"
          >
            文档炼题
          </button>
          <button
            :class="{ active: route.path === '/my-banks' }"
            @click="navigate('/my-banks')"
          >
            我的题库
          </button>
          <button
            :class="{ active: route.path === '/records' }"
            @click="navigate('/records')"
          >
            练习记录
          </button>
          <button
            :class="{ active: route.path === '/wrong-questions' }"
            @click="navigate('/wrong-questions')"
          >
            错题本
          </button>
        </nav>

        <div class="header-actions">
          <template v-if="user">
            <el-dropdown trigger="click" popper-class="header-dropdown">
              <div class="user-trigger">
                <el-avatar :size="34" src="/favicon.png" class="user-avatar" />
                <span class="user-name">{{ user.username }}</span>
                <el-icon><ArrowDown /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="user?.role === 'admin'" @click="navigate('/admin')">
                    <el-icon><Setting /></el-icon>平台题库管理
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="logout">
                    <el-icon><SwitchButton /></el-icon>退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-else>
            <el-button type="primary" size="small" class="login-btn" @click="router.push('/login')">登录 / 注册</el-button>
          </template>
          <button class="menu-toggle" @click="menuOpen = !menuOpen" aria-label="切换菜单">
            <el-icon><Menu /></el-icon>
          </button>
        </div>
      </div>
    </header>

    <!-- 移动端菜单遮罩 -->
    <div
      v-if="route.path !== '/login'"
      class="drawer-overlay"
      :class="{ open: menuOpen }"
      @click="menuOpen = false"
    />

    <main :class="{ content: route.path !== '/login' }"><router-view /></main>

    <!-- 客服/用户群入口 -->
    <button
      v-if="route.path !== '/login'"
      class="wechat-float"
      aria-label="加入用户群、客服反馈"
      @click="qrVisible = true"
    >
      <el-icon><Service /></el-icon>
      <span class="wechat-float-text">用户群</span>
    </button>

    <el-dialog
      v-model="qrVisible"
      title="加入 TILIAN 题炼用户群"
      width="320px"
      align-center
      class="qr-dialog"
    >
      <div class="qr-body">
        <img src="/wechat-qr.png" alt="TILIAN 题炼用户群微信二维码">
        <p>扫码添加客服微信</p>
        <p class="qr-hint">进群交流、产品反馈、问题咨询</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UserFilled, Setting, Menu, SwitchButton, ArrowDown, Service } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const user = ref(null)
const qrVisible = ref(false)

const loadUser = () => {
  try {
    user.value = JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    user.value = null
  }
}

onMounted(loadUser)
watch(() => route.path, loadUser)

const menuOpen = ref(false)

const navigate = (path) => {
  menuOpen.value = false
  router.push(path)
}

const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  user.value = null
  menuOpen.value = false
  router.push('/login')
}
</script>
