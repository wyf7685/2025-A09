<script setup lang="ts">
import { useLoginStore } from '@/stores/login';
import { ChatDotRound, House, Lightning, Link, Menu } from '@element-plus/icons-vue';
import { Icon } from '@iconify/vue';
import { ElAside, ElButton, ElIcon, ElTooltip } from 'element-plus';
import { RouterLink } from 'vue-router';

defineProps<{
  apiStatus: boolean;
  sidebarCollapsed: boolean;
  sidebarTransitioning: boolean;
}>();

const emit = defineEmits<{
  toggleSidebar: [];
}>();

const loginStore = useLoginStore();
</script>

<template>
  <el-aside :class="['layout-sidebar', { collapsed: sidebarCollapsed }]">
    <!-- 侧边栏顶部区域：平台标题和折叠按钮 -->
    <div class="sidebar-header">
      <div v-if="!sidebarCollapsed" class="platform-info">
        <h1 class="platform-title">
          智能数据分析平台
        </h1>
      </div>
      <el-tooltip :content="sidebarCollapsed ? '展开' : '收起'"
        placement="right">
        <el-icon @click="emit('toggleSidebar')">
          <Menu />
        </el-icon>
      </el-tooltip>
    </div>

    <div class="sidebar-menu">
      <div :class="['custom-menu', { collapsed: sidebarCollapsed }]">
        <RouterLink v-for="(item, index) in [
          { path: '/dashboard', icon: House, label: '工作台', type: 'element' },
          { path: '/data-management', icon: 'tabler:database', label: '数据管理', type: 'iconify' },
          { path: '/data-upload', icon: 'tabler:cloud-upload', label: '数据上传', type: 'iconify' },
          { path: '/chat-analysis', icon: ChatDotRound, label: '对话分析', type: 'element' },
          { path: '/mcp-connections', icon: Link, label: 'MCP连接', type: 'element' },
          { path: '/llm-models', icon: 'tabler:robot', label: '大语言模型', type: 'iconify' },
          { path: '/trained-models', icon: 'tabler:chart-dots', label: '机器学习模型', type: 'iconify' }
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
            <div class="menu-icon">
              <Icon v-if="item.type === 'iconify'" :icon="item.icon as string" />
              <el-icon v-else>
                <component :is="item.icon" />
              </el-icon>
            </div>
          </el-tooltip>
          <div v-else class="menu-icon">
            <Icon v-if="item.type === 'iconify'" :icon="item.icon as string" />
            <el-icon v-else>
              <component :is="item.icon" />
            </el-icon>
          </div>
          <Transition name="label-fade">
            <span v-if="!sidebarCollapsed && !sidebarTransitioning" class="menu-label">{{ item.label }}</span>
          </Transition>
        </RouterLink>
      </div>
    </div>

    <!-- 添加底部状态指示器 -->
    <div class="sidebar-footer">
      <div v-if="!sidebarCollapsed" class="status-wrapper">
        <div class="status-indicators">
          <div class="status-item">
            <el-icon class="status-icon" :class="{ active: apiStatus }">
              <Lightning />
            </el-icon>
            <span class="status-label">API: {{ apiStatus ? '在线' : '离线' }}</span>
          </div>
        </div>

        <!-- 登出按钮 -->
        <el-button
          type="danger"
          class="logout-button"
          @click="loginStore.logout()">
          <Icon icon="material-symbols:logout-rounded"></Icon>
          <span>退出登录</span>
        </el-button>
      </div>
      <div v-else class="status-indicators-collapsed">
        <el-tooltip content="API: 在线" placement="right" v-if="apiStatus">
          <el-icon class="status-icon active">
            <Lightning />
          </el-icon>
        </el-tooltip>
        <el-tooltip content="API: 离线" placement="right" v-else>
          <el-icon class="status-icon">
            <Lightning />
          </el-icon>
        </el-tooltip>
      </div>
    </div>
  </el-aside>
</template>

<style lang="scss" scoped>
.layout-sidebar {
  width: 220px;
  background: rgba(27, 38, 54, 0.95);
  border-right: 1px solid rgba(30, 41, 59, 0.8);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  backdrop-filter: blur(10px);
  will-change: width;
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  height: 100vh;
  z-index: 10;
}

.layout-content {
  flex: 1;
  padding: 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  overflow-y: auto;
  margin-left: 220px;
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-height: 100vh;
  box-sizing: border-box;
}

/* 侧边栏收缩状态下的内容区域 */
.layout-sidebar.collapsed+.layout-content {
  margin-left: 64px;
}

/* 侧边栏顶部标题区域 */
.sidebar-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.platform-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.platform-title {
  font-size: 18px;
  font-weight: 500;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-menu {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex: 1;
}

/* 底部状态指示器样式 */
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  background-color: rgba(20, 29, 41, 0.95);
}

.status-indicators {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-indicators-collapsed {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-icon {
  font-size: 16px;
  color: #64748b;
}

.status-icon.active {
  color: #10b981;
}

.status-label {
  font-size: 14px;
  color: #94a3b8;
}

/* 状态栏包装器 */
.status-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

/* 登出按钮样式 */
.logout-button {
  height: 32px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #ef4444;
  font-size: 12px;
}

.logout-button:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
}

.layout-sidebar.collapsed {
  width: 64px;
}

.layout-sidebar.collapsed .sidebar-header {
  justify-content: center;
  padding: 16px 0;
}

/* 图标样式 */
.menu-icon {
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
}

.menu-icon .el-icon {
  font-size: 18px;
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
  color: #e2e8f0;
  text-decoration: none;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-weight: 500;
  gap: 12px;
  position: relative;
  overflow: hidden;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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
