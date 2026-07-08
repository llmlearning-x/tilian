<template>
  <div class="landing">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-badge">TILIAN 题炼</div>
        <h1>
          把资料，炼成题库。
        </h1>
        <p class="hero-desc">
          题炼是一款面向学生的题库练习产品。你可以直接使用平台题库刷题，也可以上传自己的学习资料，生成专属题库。
        </p>
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="start">
            {{ user ? '开始练习' : '免费使用' }}
          </el-button>
          <el-button size="large" @click="router.push('/generate')">
            文档炼题
          </el-button>
        </div>
      </div>
      <div class="hero-cards">
        <div class="floating-card card-1">
          <el-icon><Document /></el-icon>
          <span>上传学习资料</span>
        </div>
        <div class="floating-card card-2">
          <el-icon><MagicStick /></el-icon>
          <span>AI 自动出题</span>
        </div>
        <div class="floating-card card-3">
          <el-icon><Collection /></el-icon>
          <span>专属题库练习</span>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section class="features">
      <div class="section-head">
        <p class="eyebrow">FEATURES</p>
        <h2>两种刷题方式，满足不同场景</h2>
      </div>
      <div class="feature-grid">
        <article class="feature-card">
          <div class="feature-icon blue">
            <el-icon><Collection /></el-icon>
          </div>
          <h3>平台题库</h3>
          <p>直接使用平台精选题库，覆盖常见知识点，打开即可练习。</p>
        </article>
        <article class="feature-card">
          <div class="feature-icon purple">
            <el-icon><Document /></el-icon>
          </div>
          <h3>文档炼题</h3>
          <p>上传 PDF、Word、Markdown 等学习资料，AI 自动提炼考点并生成专属题库。</p>
        </article>
        <article class="feature-card">
          <div class="feature-icon teal">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <h3>练习记录</h3>
          <p>每次练习自动记录正确率与进度，帮助你追踪学习效果。</p>
        </article>
      </div>
    </section>

    <!-- CTA -->
    <section class="landing-cta">
      <div class="cta-inner">
        <h2>准备好开始高效练习了吗？</h2>
        <p>现在就加入 TILIAN 题炼，让每一份学习资料都变成可练习的题目。</p>
        <el-button type="primary" size="large" @click="start">
          {{ user ? '进入题库' : '免费注册' }}
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Document, Collection, MagicStick, DataAnalysis } from '@element-plus/icons-vue'

const router = useRouter()
const user = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
})

const start = () => {
  router.push(user.value ? '/banks' : '/login')
}
</script>

<style scoped>
.hero {
  position: relative;
  max-width: var(--page-max-width);
  margin: 0 auto;
  padding: var(--space-16) var(--space-8);
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: var(--space-10);
  align-items: center;
  min-height: calc(100vh - var(--header-height));
}

.hero-inner {
  max-width: 620px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: 999px;
  background: var(--primary-light);
  color: var(--primary);
  font-size: var(--text-sm);
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: var(--space-6);
}

.hero h1 {
  font: 900 var(--text-7xl) / 1.1 var(--font-sans);
  margin: 0 0 var(--space-6);
  color: var(--gray-900);
  letter-spacing: -0.03em;
}

.hero-desc {
  font-size: var(--text-lg);
  line-height: 1.8;
  color: var(--gray-600);
  margin: 0 0 var(--space-8);
}

.hero-actions {
  display: flex;
  gap: var(--space-4);
}

.hero-actions .el-button {
  min-width: 132px;
}

.hero-cards {
  position: relative;
  min-height: 360px;
}

.floating-card {
  position: absolute;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  background: #fff;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  font-weight: 600;
  color: var(--gray-800);
}

.floating-card .el-icon {
  font-size: var(--text-2xl);
  color: var(--primary);
}

.card-1 { top: 10%; left: 5%; animation: float 5s ease-in-out infinite; }
.card-2 { top: 40%; right: 0; animation: float 6s ease-in-out infinite 0.5s; }
.card-3 { bottom: 5%; left: 20%; animation: float 5.5s ease-in-out infinite 1s; }

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}

.features {
  max-width: var(--page-max-width);
  margin: 0 auto;
  padding: var(--space-16) var(--space-8);
}

.section-head {
  text-align: center;
  max-width: 640px;
  margin: 0 auto var(--space-10);
}

.section-head h2 {
  font: 700 var(--text-4xl) / 1.2 var(--font-sans);
  margin: var(--space-3) 0 0;
  color: var(--gray-900);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-6);
}

.feature-card {
  background: #fff;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-2xl);
  padding: var(--space-8);
  box-shadow: var(--shadow-card);
  transition: all var(--transition-base);
}

.feature-card:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-4px);
  border-color: var(--brand-200);
}

.feature-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-3xl);
  margin-bottom: var(--space-5);
}

.feature-icon.blue { background: var(--primary-light); color: var(--primary); }
.feature-icon.purple { background: #f3e8ff; color: #9333ea; }
.feature-icon.teal { background: #f0fdfa; color: #0d9488; }

.feature-card h3 {
  font: 700 var(--text-2xl) var(--font-sans);
  margin: 0 0 var(--space-3);
  color: var(--gray-900);
}

.feature-card p {
  margin: 0;
  color: var(--gray-600);
  line-height: 1.7;
}

.landing-cta {
  background: linear-gradient(135deg, #0b0c0f 0%, #312e81 50%, #4f46e5 100%);
  color: #fff;
  padding: var(--space-16) var(--space-8);
}

.cta-inner {
  max-width: 720px;
  margin: 0 auto;
  text-align: center;
}

.cta-inner h2 {
  font: 700 var(--text-4xl) / 1.2 var(--font-sans);
  margin: 0 0 var(--space-4);
}

.cta-inner p {
  font-size: var(--text-lg);
  opacity: 0.85;
  margin: 0 0 var(--space-8);
}

@media (max-width: 1024px) {
  .hero {
    grid-template-columns: 1fr;
    text-align: center;
    padding: var(--space-12) var(--space-6);
  }

  .hero-inner {
    max-width: 640px;
    margin: 0 auto;
  }

  .hero-actions {
    justify-content: center;
  }

  .hero-cards {
    display: none;
  }

  .feature-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .hero {
    min-height: auto;
    padding: var(--space-10) var(--space-4);
  }

  .hero h1 {
    font-size: var(--text-4xl);
  }

  .hero-desc {
    font-size: var(--text-base);
  }

  .hero-actions {
    flex-direction: column;
  }

  .hero-actions .el-button {
    width: 100%;
  }

  .features {
    padding: var(--space-10) var(--space-4);
  }

  .section-head h2 {
    font-size: var(--text-3xl);
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .landing-cta {
    padding: var(--space-10) var(--space-4);
  }

  .cta-inner h2 {
    font-size: var(--text-3xl);
  }
}

@media (max-width: 480px) {
  .hero {
    padding: var(--space-8) var(--space-4);
  }

  .hero h1 {
    font-size: var(--text-3xl);
  }

  .hero-badge {
    font-size: var(--text-xs);
  }

  .feature-card {
    padding: var(--space-5);
  }

  .feature-icon {
    width: 48px;
    height: 48px;
    font-size: var(--text-2xl);
  }

  .feature-card h3 {
    font-size: var(--text-lg);
  }
}
</style>
