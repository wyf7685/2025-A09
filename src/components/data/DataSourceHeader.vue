<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue';
import { DocumentAdd, Refresh } from '@element-plus/icons-vue';
import { ElButton } from 'element-plus';

// 定义组件属性，带类型标注
defineProps<{
  isLoading: boolean;
}>();

// 定义组件事件，带类型标注
const emit = defineEmits<{
  refresh: [];
}>();
</script>

<template>
  <div class="page-header">
    <PageHeader
      title="数据源管理"
      subtitle="上传、管理和分析您的数据源" />
    <div class="header-actions">
      <el-button type="primary" :icon="DocumentAdd" @click="$router.push('/data-upload')">
        添加数据源
      </el-button>
      <el-button :icon="Refresh" @click="emit('refresh')" :loading="isLoading">
        刷新列表
      </el-button>
    </div>
  </div>
</template>
<style lang="scss" scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding: 0 8px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

// 响应式设计
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }
}
</style>
