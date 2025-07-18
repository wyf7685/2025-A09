<script setup lang="ts">
import { useDataSourceStore } from '@/stores/datasource';
import { DocumentCopy } from '@element-plus/icons-vue';
import { onMounted, ref } from 'vue';

const visible = defineModel<boolean>('visible', { required: true });

const emit = defineEmits<{
  'create-session': [sourceIds: string[]]; // 修改为接收字符串数组
  'go-to-data': [];                     // 前往数据管理
}>();

const dataSourceStore = useDataSourceStore();

// 已选择的数据集ID数组
const selectedDatasets = ref<string[]>([]);

// 选择/取消选择数据集
const toggleDatasetSelection = (sourceId: string) => {
  const index = selectedDatasets.value.indexOf(sourceId);
  if (index === -1) {
    // 未选中，添加到选择列表
    selectedDatasets.value.push(sourceId);
  } else {
    // 已选中，从选择列表移除
    selectedDatasets.value.splice(index, 1);
  }
};

// 使用选中的数据集创建会话
const createSessionWithSelectedDatasets = () => {
  if (selectedDatasets.value.length === 0) {
    return; // 如果没有选中的数据集，不执行操作
  }
  emit('create-session', selectedDatasets.value);
};

// 单个数据集快速选择（保留向后兼容性）
const quickSelectDataset = (sourceId: string) => {
  emit('create-session', [sourceId]);
};

// 前往数据管理
const goToAddData = () => {
  emit('go-to-data');
};

// 关闭对话框
const closeDialog = () => {
  visible.value = false;
  // 清空选择
  selectedDatasets.value = [];
};

// 组件挂载时加载数据源
onMounted(() => {
  dataSourceStore.listDataSources().catch(error => {
    console.error('加载数据源失败:', error);
  });
});
</script>

<template>
  <el-dialog v-model="visible" title="选择数据集以创建会话" width="600px" @closed="closeDialog">
    <el-empty v-if="!Object.keys(dataSourceStore.dataSources).length" description="暂无数据集，请先上传或选择一个数据集。">
      <el-button type="primary" @click="goToAddData">前往添加数据集</el-button>
    </el-empty>

    <div v-else>
      <!-- 已选数据集计数和操作按钮 -->
      <div class="selected-datasets-info">
        <div class="selected-count">
          已选择 {{ selectedDatasets.length }} 个数据集
        </div>
        <el-tooltip :content="selectedDatasets.length === 0 ? '至少需要选择一个数据集' : `选择 ${selectedDatasets.length} 个数据集创建会话`"
          placement="top">
          <el-button type="primary" @click="createSessionWithSelectedDatasets"
            :disabled="selectedDatasets.length === 0">
            创建会话
          </el-button>
        </el-tooltip>
      </div>

      <div class="dataset-list">
        <div v-for="[sourceId, metadata] in Object.entries(dataSourceStore.dataSources)" :key="sourceId"
          class="dataset-item" :class="{ 'dataset-selected': selectedDatasets.includes(sourceId) }"
          @click="toggleDatasetSelection(sourceId)">
          <div class="dataset-info">
            <el-icon>
              <DocumentCopy />
            </el-icon>
            <div class="dataset-details">
              <div class="dataset-name">{{ metadata.name || `数据集 ${sourceId.slice(0, 8)}...` }}</div>
              <div class="dataset-description">{{ metadata.description || '暂无描述' }}</div>
            </div>
          </div>
          <el-button type="primary" size="small" @click.stop="quickSelectDataset(sourceId)">快速选择</el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="closeDialog">取消</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.selected-datasets-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0 16px;
  margin-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;

  .selected-count {
    font-weight: 500;
    color: #10b981;
  }
}

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

    &.dataset-selected {
      background-color: #ecfdf5;
      border-color: #10b981;
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
