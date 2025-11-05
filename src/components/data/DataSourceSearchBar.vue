<script setup lang="ts">
import { turncateString } from '@/utils/tools';
import { ArrowRight, DocumentChecked, EditPen, Search } from '@element-plus/icons-vue';
import { ElButton, ElCard, ElIcon, ElInput, ElMessage, ElTag, ElTooltip } from 'element-plus';

// 使用 defineModel 实现双向绑定
const searchQuery = defineModel<string>('searchQuery', { required: true });

// 获取props
const props = defineProps<{
  selectedSources: string[];
  sourceNames: Record<string, string>;
}>();

// 定义组件事件
const emit = defineEmits<{
  createSession: [];
}>();

// 创建会话
const createSessionWithSelectedSources = () => {
  if (props.selectedSources.length === 0) {
    ElMessage.warning('请至少选择一个数据集');
    return;
  }

  emit('createSession');
};


// 获取展示的数据源名称
const getDatasourceName = (sourceId: string): string => {
  return props.sourceNames[sourceId] || `${sourceId.slice(0, 8)}...`;
};
</script>

<template>
  <div class="search-section">
    <el-card shadow="never">
      <div class="search-header">
        <div class="header-left">
          <h3>数据源列表</h3>
          <el-tooltip
            :content="selectedSources.length === 0 ? '请至少选择一个数据集' : `使用选定的 ${selectedSources.length} 个数据集开始分析`"
            placement="top">
            <el-button type="primary" @click="createSessionWithSelectedSources" :disabled="selectedSources.length === 0"
              class="analysis-button">
              开始分析
              <el-icon class="el-icon--right">
                <ArrowRight />
              </el-icon>
            </el-button>
          </el-tooltip>
        </div>
        <div class="search-controls">
          <el-input v-model="searchQuery" placeholder="搜索数据源名称或描述..." :prefix-icon="Search" clearable
            style="width: 300px;" />
        </div>
      </div>

      <!-- 已选择数据集 -->
      <div class="selection-actions">
        <div class="selection-info">
          <el-tag :type="selectedSources.length > 0 ? 'success' : 'info'" class="selection-tag">
            <template v-if="selectedSources.length > 0">
              <el-icon>
                <DocumentChecked />
              </el-icon>
              已选择 {{ selectedSources.length }} 个数据集
            </template>
            <template v-else>
              <el-icon>
                <EditPen />
              </el-icon>
              选择数据集进行分析...
            </template>
          </el-tag>

          <div class="selected-datasets" v-if="selectedSources.length > 0">
            <el-tag v-for="sourceId in selectedSources.slice(0, 3)" :key="sourceId" class="dataset-tag">
              {{ turncateString(getDatasourceName(sourceId), 20) }}
            </el-tag>
            <el-tag v-if="selectedSources.length > 3" type="info">
              +{{ selectedSources.length - 3 }} 个
            </el-tag>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.search-section {
  margin-bottom: 24px;

  .el-card {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    border: none;

    :deep(.el-card__body) {
      padding: 24px;
    }

    .search-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-left {
        display: flex;
        align-items: center;
        gap: 16px;

        h3 {
          margin: 0;
          font-size: 20px;
          font-weight: 600;
          color: #374151;
        }

        .analysis-button {
          border-radius: 20px;
          font-weight: 500;
        }
      }

      .search-controls {
        .el-input {
          :deep(.el-input__wrapper) {
            border-radius: 25px;
            padding: 8px 16px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
          }
        }
      }
    }
  }
}

.selection-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f0f9ff;
  padding: 12px 16px;
  border-radius: 8px;
  margin-top: 16px;
  border: 1px solid #bae6fd;

  .selection-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;

    .selection-tag {
      background: #0ea5e9;
      color: white;
      border: none;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 4px;

      .el-icon {
        margin-right: 4px;
      }
    }

    .selected-datasets {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      .dataset-tag {
        max-width: 200px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        background: white;
        border: 1px solid #bae6fd;
        color: #0284c7;
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .search-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;

    .header-left {
      width: 100%;
      justify-content: space-between;
    }

    .search-controls {
      width: 100%;

      .el-input {
        width: 100% !important;
      }
    }
  }

  .selection-actions {
    flex-direction: column;
    gap: 12px;

    .selection-info {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }
  }
}
</style>
