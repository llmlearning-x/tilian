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
                <el-avatar :size="34" :src="baseUrl + 'favicon.png'" class="user-avatar" />
                <span class="user-name">{{ user.username }}</span>
                <el-icon><ArrowDown /></el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="user?.role === 'admin'" @click="navigate('/admin')">
                    <el-icon><Setting /></el-icon>平台题库管理
                  </el-dropdown-item>
                  <el-dropdown-item @click="passwordVisible = true">
                    <el-icon><Lock /></el-icon>修改密码
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
        <img :src="baseUrl + 'wechat-qr.png'" alt="TILIAN 题炼用户群微信二维码">
        <p>扫码添加客服微信</p>
        <p class="qr-hint">进群交流、产品反馈、问题咨询</p>
      </div>
    </el-dialog>

    <el-dialog
      v-model="passwordVisible"
      title="修改密码"
      width="400px"
      align-center
      class="password-dialog"
    >
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-position="top"
      >
        <el-form-item label="当前密码" prop="currentPassword">
          <el-input
            v-model="passwordForm.currentPassword"
            type="password"
            placeholder="请输入当前密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="passwordForm.newPassword"
            type="password"
            placeholder="请输入新密码（至少6位）"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" @click="submitChangePassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UserFilled, Setting, Menu, SwitchButton, ArrowDown, Service, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/modules'

const route = useRoute()
const router = useRouter()
const baseUrl = import.meta.env.BASE_URL
const user = ref(null)
const qrVisible = ref(false)
const passwordVisible = ref(false)
const passwordFormRef = ref()
const passwordForm = ref({ currentPassword: '', newPassword: '', confirmPassword: '' })
const passwordRules = {
  currentPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.value.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

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

const submitChangePassword = async () => {
  if (!passwordFormRef.value) return
  passwordFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      await authApi.changePassword({
        current_password: passwordForm.value.currentPassword,
        new_password: passwordForm.value.newPassword
      })
      ElMessage.success('密码修改成功，请重新登录')
      passwordVisible.value = false
      passwordForm.value = { currentPassword: '', newPassword: '', confirmPassword: '' }
      logout()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '密码修改失败')
    }
  })
}
</script>
