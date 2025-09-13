<script setup lang="ts">
import { checkHealth as checkHealthApi } from '@/utils/api';
import { ChatDotRound, Collection, Connection, DataAnalysis, House, Link, Menu, Monitor } from '@element-plus/icons-vue';
import { ElAside, ElBadge, ElButton, ElHeader, ElIcon, ElMenu, ElMenuItem } from 'element-plus';
import { KeepAlive, onMounted, ref, Suspense, Transition } from 'vue';
import { RouterLink, RouterView } from 'vue-router';

// 响应式数据
const sidebarCollapsed = ref(false);
const healthStatus = ref(false);

// 方法
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value;
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
      <el-aside :class="['layout-sidebar', { collapsed: sidebarCollapsed }]"
        :width="sidebarCollapsed ? '60px' : '250px'">
        <div class="sidebar-menu">
          <!-- 未折叠状态下的菜单 -->
          <div v-if="!sidebarCollapsed" class="expanded-menu">
            <el-menu :default-active="$route.path" router background-color="#ffffff"
              text-color="#333" active-text-color="#409EFF">
              <el-menu-item index="/dashboard">
                <el-icon>
                  <House />
                </el-icon>
                <span>工作台</span>
              </el-menu-item>

              <el-menu-item index="/data-management">
                <el-icon>
                  <Collection />
                </el-icon>
                <span>数据管理</span>
              </el-menu-item>

              <el-menu-item index="/data-upload">
                <el-icon>
                  <Connection />
                </el-icon>
                <span>数据上传</span>
              </el-menu-item>

              <el-menu-item index="/chat-analysis">
                <el-icon>
                  <ChatDotRound />
                </el-icon>
                <span>对话分析</span>
              </el-menu-item>

              <el-menu-item index="/mcp-connections">
                <el-icon>
                  <Link />
                </el-icon>
                <span>MCP连接</span>
              </el-menu-item>

              <el-menu-item index="/llm-models">
                <el-icon>
                  <Connection />
                </el-icon>
                <span>大语言模型</span>
              </el-menu-item>

              <el-menu-item index="/trained-models">
                <el-icon>
                  <DataAnalysis />
                </el-icon>
                <span>机器学习模型</span>
              </el-menu-item>
            </el-menu>
          </div>

          <!-- 折叠状态下的菜单 -->
          <div v-else class="collapsed-menu">
            <RouterLink v-for="(item, index) in [
              { path: '/dashboard', icon: House },
              { path: '/data-management', icon: Collection },
              { path: '/data-upload', icon: Connection },
              { path: '/chat-analysis', icon: ChatDotRound },
              { path: '/mcp-connections', icon: Link },
              { path: '/llm-models', icon: Connection },
              { path: '/trained-models', icon: DataAnalysis }
            ]" :key="index" :to="item.path" class="collapsed-menu-item" :class="{ active: $route.path === item.path }">
              <el-icon>
                <component :is="item.icon" />
              </el-icon>
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
  background: rgba(255, 255, 255, 0.95);
  border-right: 1px solid rgba(226, 232, 240, 0.8);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  backdrop-filter: blur(10px);
}

.sidebar-menu {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.layout-sidebar.collapsed {
  width: 60px !important;
}

.layout-content {
  flex: 1;
  padding: 10px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  overflow-y: auto;
}

/* 展开菜单样式 */
.expanded-menu .el-menu {
  border-right: none;
  background: transparent !important;
  width: 100%;
}

.expanded-menu .el-menu-item {
  border-radius: 12px;
  margin: 6px 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-weight: 500;
  color: #64748b;
  display: flex;
  align-items: center;
}

.expanded-menu .el-menu-item:hover {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.expanded-menu .el-menu-item.is-active {
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  color: white !important;
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.25);
}

.expanded-menu .el-menu-item.is-active:hover {
  transform: translateX(4px);
}

/* 折叠菜单样式 */
.collapsed-menu {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 0;
  overflow-y: auto;
  height: 100%;
}

.collapsed-menu-item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin: 8px 0;
  border-radius: 50%;
  color: #64748b;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.collapsed-menu-item:hover {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.collapsed-menu-item.active {
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  color: white;
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.25);
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
