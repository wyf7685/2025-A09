<script setup lang="ts">
import AppSidebar from '@/components/AppSidebar.vue';
import { persistConfig } from '@/utils/tools';
import { ref } from 'vue';

defineProps<{
  apiStatus: boolean;
}>();

const sidebarCollapsed = persistConfig('appSidebarCollapsed', false);
const sidebarTransitioning = ref(false);

// 方法
const toggleSidebar = () => {
  sidebarTransitioning.value = true;
  sidebarCollapsed.value = !sidebarCollapsed.value;
  setTimeout(() => {
    sidebarTransitioning.value = false;
  }, 300); // 与CSS过渡时间同步
};
</script>

<template>
  <div class="layout-main">
    <!-- 侧边栏 -->
    <AppSidebar
      :api-status="apiStatus"
      :sidebar-collapsed="sidebarCollapsed"
      :sidebar-transitioning="sidebarTransitioning"
      @toggleSidebar="toggleSidebar" />

    <!-- 内容区域 -->
    <main class="layout-content" :style="{ marginLeft: sidebarCollapsed ? '64px' : undefined }">
      <slot></slot>
    </main>
  </div>
</template>

<style lang="scss" scoped>
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

/* Tooltip 样式 */
:deep(.el-tooltip__popper) {
  font-weight: 500;
  padding: 6px 10px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
