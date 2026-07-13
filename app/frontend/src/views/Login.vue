<template>
  <div class="login-page">
    <div class="login-hero">
      <div class="login-hero-content">
        <div class="login-brand">
          <span class="brand-mark">TILIAN</span>
          <span>题炼</span>
        </div>
        <h1>把资料，<br>炼成题库。</h1>
        <p>题炼是一款面向学习者的题库练习产品。你可以直接使用平台题库刷题，也可以上传自己的学习资料，生成专属题库。</p>
        <div class="login-features">
          <div class="feature-item">
            <span class="feature-icon"><el-icon><Collection /></el-icon></span>
            <span>平台题库在线练习</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon"><el-icon><Document /></el-icon></span>
            <span>上传资料生成专属题库</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon"><el-icon><TrendCharts /></el-icon></span>
            <span>练习记录与正确率追踪</span>
          </div>
        </div>
      </div>
    </div>

    <div class="login-form-section">
      <!-- 移动端品牌头 -->
      <div class="mobile-login-brand">
        <span class="brand-mark">TILIAN</span>
        <div>
          <div class="brand-name">题炼</div>
          <div class="brand-slogan">把资料，炼成题库</div>
        </div>
      </div>

      <div class="login-container">
        <el-card class="login-card" shadow="never">
          <el-tabs v-model="activeTab" stretch>
            <el-tab-pane label="登录" name="login">
              <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-width="0" @submit.prevent="handleLogin">
                <el-form-item prop="username">
                  <el-input v-model="loginForm.username" placeholder="用户名" prefix-icon="User" size="large" />
                </el-form-item>
                <el-form-item prop="password">
                  <el-input v-model="loginForm.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password @keyup.enter="handleLogin" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="handleLogin">
                    登录
                  </el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="注册" name="register">
              <el-form ref="registerFormRef" :model="registerForm" :rules="registerRules" label-width="0" @submit.prevent="handleRegister">
                <el-form-item prop="username">
                  <el-input v-model="registerForm.username" placeholder="用户名" prefix-icon="User" size="large" />
                </el-form-item>
                <el-form-item prop="email">
                  <el-input v-model="registerForm.email" placeholder="邮箱" prefix-icon="Message" size="large" />
                </el-form-item>
                <el-form-item prop="password">
                  <el-input v-model="registerForm.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password />
                </el-form-item>
                <el-form-item prop="confirmPassword">
                  <el-input v-model="registerForm.confirmPassword" type="password" placeholder="确认密码" prefix-icon="Lock" size="large" show-password />
                </el-form-item>
                <el-form-item prop="inviteCode">
                  <el-input v-model="registerForm.inviteCode" placeholder="邀请码" prefix-icon="Ticket" size="large" @keyup.enter="handleRegister" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="handleRegister">
                    注册
                  </el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <div class="login-footer">
          <p>演示账号：demo / demo123</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/modules'
import { Collection, Document, Ticket, TrendCharts } from '@element-plus/icons-vue'

const router = useRouter()
const activeTab = ref('login')
const loading = ref(false)

const loginFormRef = ref()
const loginForm = reactive({ username: '', password: '' })
const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const registerFormRef = ref()
const registerForm = reactive({ username: '', email: '', password: '', confirmPassword: '', inviteCode: '' })
const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  inviteCode: [
    { required: true, message: '请输入邀请码', trigger: 'blur' },
    { min: 1, max: 64, message: '邀请码长度不能超过 64 个字符', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await authApi.login(loginForm)
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('user', JSON.stringify(res.data.user))
      ElMessage.success('登录成功')
      router.push({ name: 'Banks' })
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '登录失败')
    } finally {
      loading.value = false
    }
  })
}

const handleRegister = async () => {
  if (!registerFormRef.value) return
  await registerFormRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await authApi.register({
        username: registerForm.username,
        email: registerForm.email,
        password: registerForm.password,
        invite_code: registerForm.inviteCode.trim()
      })
      ElMessage.success('注册成功，请登录')
      activeTab.value = 'login'
      registerFormRef.value.resetFields()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '注册失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-brand .brand-mark,
.mobile-login-brand .brand-mark {
  font: 800 var(--text-md) var(--font-sans);
  letter-spacing: 0.06em;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--violet-500) 100%);
  padding: 6px 10px;
  border-radius: 12px;
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.35);
}

.mobile-login-brand {
  display: none;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 0 0 28px;
  width: 100%;
  padding: 28px;
  border-radius: var(--radius-xl);
  background: linear-gradient(135deg, #0b0c0f 0%, #312e81 50%, #4f46e5 100%);
  color: #fff;
  box-shadow: var(--shadow-lg);
  position: relative;
  overflow: hidden;
}

.mobile-login-brand::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 80%, rgba(99, 102, 241, 0.35) 0%, transparent 50%),
              radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.3) 0%, transparent 50%);
}

.mobile-login-brand .brand-mark {
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.mobile-login-brand > div {
  position: relative;
  z-index: 1;
}

.mobile-login-brand .brand-name {
  font-size: var(--text-2xl);
  font-weight: 800;
  color: #fff;
  line-height: 1.3;
}

.mobile-login-brand .brand-slogan {
  font-size: var(--text-sm);
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.4;
}

@media (max-width: 1024px) {
  .mobile-login-brand {
    display: flex;
  }
}
</style>
