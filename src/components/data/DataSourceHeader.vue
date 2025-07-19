<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue';

// 定义组件属性，带类型标注
defineProps<{
  isLoading: boolean;
}>();

// 定义组件事件，带类型标注
const emit = defineEmits<{
  refresh: [];
}>();

// 刷新数据的处理函数
const handleRefresh = () => {
  emit('refresh');
};
</script>

<template>
  <div class="header-section">
    <div class="header-title">
      <h1>数据源管理</h1>
      <p>上传、管理和分析您的数据源</p>
    </div>
    <div class="header-actions">
      <el-button type="primary" :icon="Refresh" @click="handleRefresh" :loading="isLoading">
        刷新列表
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;

  .header-title {
    h1 {
      font-size: 32px;
      font-weight: 700;
      color: #1f2937;
      margin: 0 0 8px 0;
      text-shadow: none;
    }

    p {
      font-size: 16px;
      color: #6b7280;
      margin: 0;
    }
  }

  .header-actions {
    .el-button {
      padding: 12px 24px;
      border-radius: 25px;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .header-section {
    flex-direction: column;
    text-align: center;
    gap: 16px;

    .header-title {
      h1 {
        font-size: 24px;
      }
    }
  }
}
</style>
