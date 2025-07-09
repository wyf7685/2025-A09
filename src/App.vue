<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import type { Session } from '@/types'


const router = useRouter()
const appStore = useAppStore()

// 响应式数据
const sidebarCollapsed = ref(false)
const currentSessionId = ref('')
const sessions = ref<Session[]>([])
const healthStatus = ref({ status: '' })

// 方法
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const createNewSession = async () => {
  try {
    const session = await appStore.createSession()
    currentSessionId.value = session.session_id
    await loadSessions()
    router.push('/dashboard')
  } catch (error) {
    console.error('创建会话失败:', error)
  }
}

const switchSession = (sessionId: string) => {
  appStore.setCurrentSession(sessionId)
}

const loadSessions = async () => {
  try {
    const response = await appStore.getSessions()
    sessions.value = response || []
  } catch (error) {
    console.error('加载会话失败:', error)
  }
}

const checkHealth = async () => {
  try {
    const status = await appStore.checkHealth()
    healthStatus.value = status
  } catch (error) {
    console.error('健康检查失败:', error)
  }
}

// 生命周期
onMounted(async () => {
  await checkHealth()
  await loadSessions()

  // 如果没有当前会话，创建一个新会话
  if (sessions.value.length === 0) {
    await createNewSession()
  } else {
    currentSessionId.value = sessions.value[0].id
    appStore.setCurrentSession(currentSessionId.value)
  }

  // 定期检查健康状态
  setInterval(checkHealth, 30 * 1000) // 每30秒检查一次
})
</script>

<template>
  <div class="layout-container">
    <!-- 顶部导航栏 -->
    <el-header class="layout-header" height="60px">
      <div style="display: flex; align-items: center; justify-content: space-between; height: 100%;">
        <div style="display: flex; align-items: center;">
          <el-button @click="toggleSidebar" type="text" style="color: white; margin-right: 16px;">
            <el-icon>
              <Menu />
            </el-icon>
          </el-button>
          <h1 style="font-size: 20px; font-weight: 500;">智能数据分析平台</h1>
        </div>

        <div style="display: flex; align-items: center; gap: 16px;">
          <!-- 会话选择器 -->
          <el-select v-model="currentSessionId" placeholder="选择会话" style="width: 200px;" @change="switchSession">
            <el-option v-for="session in sessions" :key="session.id" :label="`会话 ${session.id.slice(0, 8)}...`"
              :value="session.id" />
          </el-select>

          <el-button @click="createNewSession" type="primary" size="small">
            <el-icon>
              <Plus />
            </el-icon>
            新建会话
          </el-button>

          <!-- 系统状态 -->
          <el-badge :value="healthStatus.status ? '正常' : '异常'" :type="healthStatus.status ? 'success' : 'danger'">
            <el-icon style="color: white; font-size: 20px;">
              <Monitor />
            </el-icon>
          </el-badge>
        </div>
      </div>
    </el-header>

    <!-- 主体内容 -->
    <div class="layout-main">
      <!-- 侧边栏 -->
      <el-aside :class="['layout-sidebar', { collapsed: sidebarCollapsed }]"
        :width="sidebarCollapsed ? '64px' : '250px'">
        <el-menu :default-active="$route.path" router :collapse="sidebarCollapsed" background-color="#ffffff"
          text-color="#333" active-text-color="#409EFF">
          <el-menu-item index="/dashboard">
            <el-icon>
              <House />
            </el-icon>
            <span>工作台</span>
          </el-menu-item>

          <el-menu-item index="/data-upload">
            <el-icon>
              <Upload />
            </el-icon>
            <span>数据上传</span>
          </el-menu-item>

          <el-menu-item index="/data-sources">
            <el-icon>
              <Database />
            </el-icon>
            <span>数据源</span>
          </el-menu-item>

          <el-menu-item index="/chat-analysis">
            <el-icon>
              <ChatDotRound />
            </el-icon>
            <span>对话分析</span>
          </el-menu-item>

          <el-menu-item index="/auto-analysis">
            <el-icon>
              <DataAnalysis />
            </el-icon>
            <span>自动分析</span>
          </el-menu-item>

          <el-menu-item index="/reports">
            <el-icon>
              <Document />
            </el-icon>
            <span>分析报告</span>
          </el-menu-item>

          <el-menu-item index="/models">
            <el-icon>
              <Setting />
            </el-icon>
            <span>模型管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 内容区域 -->
      <main class="layout-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

.layout-header {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  padding: 0 24px;
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.15);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.layout-main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.layout-sidebar {
  background: rgba(255, 255, 255, 0.95);
  border-right: 1px solid rgba(226, 232, 240, 0.8);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  backdrop-filter: blur(10px);
}

.layout-sidebar.collapsed {
  width: 64px !important;
}

.layout-content {
  flex: 1;
  padding: 10px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  overflow-y: auto;
}

.el-menu {
  border-right: none;
  background: transparent !important;
}

.el-menu-item {
  border-radius: 12px;
  margin: 6px 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-weight: 500;
  color: #64748b;
}

.el-menu-item:hover {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.el-menu-item.is-active {
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  color: white !important;
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.25);
}

.el-menu-item.is-active:hover {
  transform: translateX(4px);
}

.el-select {
  border-radius: 8px;
}

.el-button {
  border-radius: 8px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.el-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
