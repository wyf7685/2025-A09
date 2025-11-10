<script setup lang="ts">
import type { DataSourceMetadataWithID } from '@/types';
import { Delete, DocumentCopy, Edit, Search, View } from '@element-plus/icons-vue';
import { ElButton, ElCard, ElIcon, ElPagination, ElTable, ElTableColumn, ElTag, ElTooltip } from 'element-plus';
import { nextTick, onMounted, ref, watch } from 'vue';

// 使用 defineModel 实现分页相关双向绑定
const currentPage = defineModel<number>('currentPage', { required: true });
const pageSize = defineModel<number>('pageSize', { required: true });

// 定义组件属性
interface Props {
  dataSources: DataSourceMetadataWithID[];
  isLoading: boolean;
  total: number;
  selectedSources: string[];
}

const props = defineProps<Props>();

// 表格引用
const tableRef = ref<InstanceType<typeof ElTable>>();

// 防止无限循环
const isUpdatingSelection = ref(false);

// 定义组件事件
const emit = defineEmits<{
  selectionChange: [selection: DataSourceMetadataWithID[]];
  edit: [source: DataSourceMetadataWithID];
  delete: [source: DataSourceMetadataWithID];
  preview: [source: DataSourceMetadataWithID];
  analyze: [source: DataSourceMetadataWithID];
}>();

// 数据源类型人类可读表示
const sourceTypeHumanRepr = (metadata: DataSourceMetadataWithID) => {
  if (!metadata.source_type.startsWith('dremio:')) {
    return metadata.source_type;
  }
  const type = metadata.source_type.split(':')[1];
  switch (type) {
    case 'PROMOTED':
    case 'FILE':
      const parts = metadata.id.split('_');
      const fileExt = parts[parts.length - 1].toLowerCase();
      return fileExt === 'csv' ? 'CSV 文件' : ['xls', 'xlsx'].includes(fileExt) ? 'Excel 文件' : 'Dremio 数据集';
    case 'DIRECT':
      return '数据库表';
  }
  return type;
};

// 获取类型标签颜色
const getTypeTagType = (source: DataSourceMetadataWithID) => {
  const type = sourceTypeHumanRepr(source);
  if (type.includes('CSV')) return 'success';
  if (type.includes('Excel')) return 'warning';
  if (type.includes('数据库')) return 'danger';
  return 'info';
};

// 处理表格选择变化
const handleSelectionChange = (selection: DataSourceMetadataWithID[]) => {
  // 防止在程序化更新选择时触发事件
  if (isUpdatingSelection.value) return;

  emit('selectionChange', selection);
};

// 根据当前选择状态设置行的选中状态
const setRowSelection = () => {
  if (!tableRef.value || isUpdatingSelection.value) return;

  // 设置标志位，防止触发 handleSelectionChange
  isUpdatingSelection.value = true;

  try {
    // 清除现有选择
    tableRef.value.clearSelection();

    // 根据 selectedSources 重新设置选中状态
    props.dataSources.forEach(row => {
      if (props.selectedSources.includes(row.source_id)) {
        tableRef.value?.toggleRowSelection(row, true);
      }
    });
  } finally {
    // 使用 nextTick 确保所有 DOM 更新完成后再重置标志位
    nextTick(() => {
      isUpdatingSelection.value = false;
    });
  }
};

// 编辑数据源
const handleEdit = (source: DataSourceMetadataWithID) => {
  emit('edit', source);
};

// 删除数据源
const handleDelete = (source: DataSourceMetadataWithID) => {
  emit('delete', source);
};

// 预览数据源
const handlePreview = (source: DataSourceMetadataWithID) => {
  emit('preview', source);
};

// 分析数据源
const handleAnalyze = (source: DataSourceMetadataWithID) => {
  emit('analyze', source);
};

// 在组件挂载后设置选中状态
onMounted(() => {
  nextTick(() => {
    setRowSelection();
  });
});

// 监听数据源变化，保持选择状态
watch(() => props.dataSources, () => {
  nextTick(() => {
    setRowSelection();
  });
}, { deep: true });

// 监听选中源变化，保持选择状态
watch(() => props.selectedSources, () => {
  nextTick(() => {
    setRowSelection();
  });
}, { deep: true });
</script>

<template>
  <div class="data-list-section">
    <el-card shadow="never">
      <el-table ref="tableRef" :data="dataSources" v-loading="isLoading" stripe class="data-table"
        @selection-change="handleSelectionChange" row-key="source_id">

        <!-- 多选列 -->
        <el-table-column type="selection" width="55" :reserve-selection="true" />

        <el-table-column prop="source_id" label="ID" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.source_id.slice(0, 8) }}...</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" min-width="200">
          <template #default="{ row }">
            <div class="name-cell">
              <el-icon class="name-icon">
                <DocumentCopy />
              </el-icon>
              <span class="name-text">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="source_type" label="类型" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="getTypeTagType(row)">
              {{ sourceTypeHumanRepr(row) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="description-text">
              {{ row.description || '暂无描述' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="统计信息" width="120" align="center">
          <template #default="{ row }">
            <div class="stats-cell">
              <el-tooltip content="行数" placement="top">
                <el-tag size="small" type="success">
                  {{ row.row_count || 'N/A' }}
                </el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="240" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <div class="action-button-row">
                <el-button size="small" type="primary" :icon="View" @click="handleAnalyze(row)" plain>
                  分析
                </el-button>
                <el-button size="small" type="success" :icon="Search" @click="handlePreview(row)" plain>
                  预览
                </el-button>
              </div>
              <div class="action-button-row">
                <el-button size="small" type="warning" :icon="Edit" @click="handleEdit(row)" plain>
                  编辑
                </el-button>
                <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(row)" plain>
                  删除
                </el-button>
              </div>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页器 -->
      <div class="pagination-section">
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[5, 10, 20, 50]"
          :small="false" :disabled="isLoading" :background="true" layout="total, sizes, prev, pager, next, jumper"
          :total="total" />
      </div>
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.data-list-section {
  .el-card {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    border: none;

    :deep(.el-card__body) {
      padding: 24px;
    }

    .data-table {
      :deep(.el-table__header) {
        background: #f8fafc;

        th {
          background: #f8fafc !important;
          color: #374151;
          font-weight: 600;
          border-bottom: 2px solid #e5e7eb;
        }
      }

      :deep(.el-table__body) {
        tr {
          transition: all 0.3s ease;

          &:hover {
            background: #f0f4ff !important;
          }
        }
      }

      .name-cell {
        display: flex;
        align-items: center;

        .name-icon {
          color: #667eea;
          margin-right: 8px;
        }

        .name-text {
          font-weight: 600;
          color: #374151;
        }
      }

      .description-text {
        color: #6b7280;
        font-size: 14px;
      }

      .stats-cell {
        display: flex;
        justify-content: center;

        .el-tag {
          border-radius: 12px;
          font-weight: 600;
        }
      }

      .action-buttons {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex-wrap: wrap;

        .action-button-row {
          display: flex;
          gap: 2px;
        }

        .el-button {
          border-radius: 20px;
          padding: 6px 12px;
          font-weight: 500;
          transition: all 0.3s ease;

          &:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          }
        }
      }
    }

    .pagination-section {
      display: flex;
      justify-content: center;
      margin-top: 24px;

      .el-pagination {
        :deep(.el-pagination__jump) {
          margin-left: 24px;
        }

        :deep(.btn-next),
        :deep(.btn-prev) {
          border-radius: 8px;
        }

        :deep(.el-pager) {
          li {
            border-radius: 8px;
            margin: 0 2px;

            &.is-active {
              background: #667eea;
              color: white;
            }
          }
        }
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .data-list-section {
    .action-buttons {
      flex-direction: column;
      gap: 4px;

      .el-button {
        width: 100%;
        font-size: 12px;
        padding: 4px 8px;
      }
    }
  }
}
</style>
