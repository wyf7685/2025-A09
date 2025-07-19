<script setup lang="ts">
import { useDataSourceStore } from '@/stores/datasource';
import { DocumentCopy } from '@element-plus/icons-vue';
import { onMounted } from 'vue';

const visible = defineModel<boolean>('visible', { required: true });

const emit = defineEmits<{
  'create-session': [sourceId: string]; // 选择数据集创建会话
  'go-to-data': [];                     // 前往数据管理
}>();

const dataSourceStore = useDataSourceStore();

// 选择数据集并创建会话
const selectDataset = (sourceId: string) => {
  emit('create-session', sourceId);
};

// 前往数据管理
const goToAddData = () => {
  emit('go-to-data');
};

// 关闭对话框
const closeDialog = () => {
  visible.value = false;
};

// 组件挂载时加载数据源
onMounted(() => {
  dataSourceStore.listDataSources().catch(error => {
    console.error('加载数据源失败:', error);
  });
});
</script>

<template>
  <el-dialog v-model="visible" title="选择数据集以创建会话" width="600px">
    <el-empty v-if="!Object.keys(dataSourceStore.dataSources).length" description="暂无数据集，请先上传或选择一个数据集。">
      <el-button type="primary" @click="goToAddData">前往添加数据集</el-button>
    </el-empty>
    <div v-else class="dataset-list">
      <div v-for="[sourceId, metadata] in Object.entries(dataSourceStore.dataSources)" :key="sourceId"
        class="dataset-item" @click="selectDataset(sourceId)">
        <div class="dataset-info">
          <el-icon>
            <DocumentCopy />
          </el-icon>
          <div class="dataset-details">
            <div class="dataset-name">{{ metadata.name || `数据集 ${sourceId.slice(0, 8)}...` }}</div>
            <div class="dataset-description">{{ metadata.description || '暂无描述' }}</div>
          </div>
        </div>
        <el-button type="primary" size="small">选择</el-button>
      </div>
    </div>
    <template #footer>
      <el-button @click="closeDialog">取消</el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.dataset-list {
  max-height: 400px;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;

    &:hover {
      background: #a8a8a8;
    }
  }

  .dataset-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    margin-bottom: 8px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      background-color: #f9fafb;
      border-color: #10b981;
      box-shadow: 0 2px 8px rgba(16, 185, 129, 0.1);
    }

    .dataset-info {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;

      .el-icon {
        color: #6b7280;
        font-size: 18px;
      }

      .dataset-details {
        .dataset-name {
          font-weight: 500;
          color: #1f2937;
          margin-bottom: 4px;
        }

        .dataset-description {
          font-size: 12px;
          color: #6b7280;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 350px;
        }
      }
    }
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .dataset-list {
    .dataset-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;

      .dataset-info {
        width: 100%;

        .dataset-details {
          .dataset-description {
            max-width: 100%;
          }
        }
      }

      .el-button {
        align-self: flex-end;
      }
    }
  }
}
</style>
