<script setup lang="ts">
import { checkHealth as checkHealthApi } from '@/utils/api';
import { ChatDotRound, Collection, Connection, DataAnalysis, House, Link, Menu, Monitor } from '@element-plus/icons-vue';
import { ElAside, ElBadge, ElButton, ElHeader, ElIcon, ElTooltip } from 'element-plus';
import { KeepAlive, onMounted, ref, Suspense, Transition } from 'vue';
import { RouterLink, RouterView } from 'vue-router';

// 响应式数据
const sidebarCollapsed = ref(false);
const healthStatus = ref(false);
const sidebarTransitioning = ref(false);

// 方法
const toggleSidebar = () => {
  sidebarTransitioning.value = true;
  sidebarCollapsed.value = !sidebarCollapsed.value;
  sidebarTransitioning.value = false;
};

const checkHealth = async () => {
  try {
    await checkHealthApi();
    healthStatus.value = true;
  } catch (error) {
    console.error('健康检查失败:', error);
    healthStatus.value = false;
  }
};

// 生命周期
onMounted(async () => {
  await checkHealth();

  // 定期检查健康状态
  setInterval(checkHealth, 3 * 60 * 1000);
});
</script>

<template>
  <div class="layout-container">
    <!-- 顶部导航栏 -->
    <el-header class="layout-header" height="50px">
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
          <!-- 系统状态 -->
          <el-badge :value="healthStatus ? '正常' : '异常'" :type="healthStatus ? 'success' : 'danger'">
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
      <el-aside :class="['layout-sidebar', { collapsed: sidebarCollapsed }]">
        <div class="sidebar-menu">
          <div :class="['custom-menu', { collapsed: sidebarCollapsed }]">
            <RouterLink v-for="(item, index) in [
              { path: '/dashboard', icon: House, label: '工作台' },
              { path: '/data-management', icon: Collection, label: '数据管理' },
              { path: '/data-upload', icon: Connection, label: '数据上传' },
              { path: '/chat-analysis', icon: ChatDotRound, label: '对话分析' },
              { path: '/mcp-connections', icon: Link, label: 'MCP连接' },
              { path: '/llm-models', icon: Connection, label: '大语言模型' },
              { path: '/trained-models', icon: DataAnalysis, label: '机器学习模型' }
            ]"
              :key="index"
              :to="item.path"
              class="menu-item"
              :class="{ active: $route.path === item.path }">
              <el-tooltip
                v-if="sidebarCollapsed"
                :content="item.label"
                placement="right"
                :offset="12"
                :show-after="300">
                <el-icon class="menu-icon">
                  <component :is="item.icon" />
                </el-icon>
              </el-tooltip>
              <el-icon v-else class="menu-icon">
                <component :is="item.icon" />
              </el-icon>
              <Transition name="label-fade">
                <span v-if="!sidebarCollapsed && !sidebarTransitioning" class="menu-label">{{ item.label }}</span>
              </Transition>
            </RouterLink>
          </div>
        </div>
      </el-aside>

      <!-- 内容区域 -->
      <main class="layout-content">
        <RouterView v-slot="{ Component }">
          <template v-if="Component">
            <Transition mode="out-in">
              <KeepAlive>
                <Suspense>
                  <!-- 主要内容 -->
                  <component :is="Component"></component>
                  <!-- 加载中状态 -->
                  <template #fallback>
                    正在加载...
                  </template>
                </Suspense>
              </KeepAlive>
            </Transition>
          </template>
        </RouterView>
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
  width: 180px;
  background: rgba(255, 255, 255, 0.95);
  border-right: 1px solid rgba(226, 232, 240, 0.8);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  backdrop-filter: blur(10px);
  will-change: width;
}

.sidebar-menu {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.layout-sidebar.collapsed {
  width: 64px;
}

/* 图标样式 */
.menu-icon {
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.layout-content {
  flex: 1;
  padding: 10px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  overflow-y: auto;
}

/* 自定义菜单样式 */
.custom-menu {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  padding: 10px 0;
  overflow-y: auto;
  transition: all 0.3s ease;
}

/* 菜单项基础样式 */
.menu-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  margin: 6px 10px;
  border-radius: 12px;
  color: #64748b;
  text-decoration: none;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-weight: 500;
  gap: 12px;
  position: relative;
  overflow: hidden;
}

.menu-item:hover {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.menu-item.active {
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.25);
}

.menu-item.active:hover {
  transform: translateX(4px);
}

.menu-label {
  font-size: 14px;
  overflow: hidden;
  white-space: nowrap;
  max-width: 180px;
}

/* 标签淡入淡出动画 */
.label-fade-enter-active {
  transition: opacity 0.3s ease 0.2s;
}

.label-fade-leave-active {
  transition: opacity 0.1s ease;
}

.label-fade-enter-from,
.label-fade-leave-to {
  opacity: 0;
}

/* 折叠菜单样式 */
.custom-menu.collapsed {
  align-items: center;
}

.custom-menu.collapsed .menu-item {
  justify-content: center;
  width: 40px;
  height: 40px;
  margin: 8px auto;
  padding: 0;
  border-radius: 50%;
}

.custom-menu.collapsed .menu-item:hover {
  transform: scale(1.05);
}

.custom-menu.collapsed .menu-item.active:hover {
  transform: scale(1.05);
}

.custom-menu.collapsed .menu-icon {
  margin: 0;
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
/* Tooltip 样式 */
:deep(.el-tooltip__popper) {
  font-weight: 500;
  padding: 6px 10px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
