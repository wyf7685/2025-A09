<script setup lang="ts">
import type { DataSourceMetadataWithID } from '@/types';

// 使用 defineModel 实现对话框可见性双向绑定
const visible = defineModel<boolean>('visible', { required: true });

// 定义组件属性
interface PaginationProps {
  current: number;
  pageSize: number;
  total: number;
}

interface Props {
  datasource: DataSourceMetadataWithID | null;
  previewData: any[];
  previewColumns: string[];
  pagination: PaginationProps;
  loading: boolean;
}

const props = defineProps<Props>();

// 定义组件事件
const emit = defineEmits<{
  loadPage: [page: number];
}>();

// 数据源类型人类可读表示
const sourceTypeHumanRepr = (metadata: DataSourceMetadataWithID | null) => {
  if (!metadata || !metadata.source_type.startsWith('dremio:')) {
    return metadata?.source_type || '';
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

// 处理分页变化
const handleCurrentChange = (page: number) => {
  emit('loadPage', page);
};

// 处理每页条数变化
const handleSizeChange = (size: number) => {
  emit('loadPage', props.pagination.current);
};
</script>

<template>
  <el-dialog v-model="visible" :title="`预览数据源: ${datasource?.name || ''}`" width="90%"
    :before-close="() => visible = false">
    <div class="preview-content">
      <div class="preview-header">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="数据源名称">
            {{ datasource?.name }}
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ datasource ? sourceTypeHumanRepr(datasource) : '' }}
          </el-descriptions-item>
          <el-descriptions-item label="总行数">
            {{ pagination.total }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="preview-table">
        <el-table :data="previewData" v-loading="loading" stripe border height="400">
          <el-table-column v-for="column in previewColumns" :key="column" :prop="column" :label="column"
            show-overflow-tooltip min-width="120" />
        </el-table>
      </div>

      <div class="preview-pagination">
        <el-pagination v-model:current-page="pagination.current" v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]" :small="false" :disabled="loading" :background="true"
          layout="total, sizes, prev, pager, next, jumper" :total="pagination.total"
          @current-change="handleCurrentChange" @size-change="handleSizeChange" />
      </div>
    </div>
  </el-dialog>
</template>

<style lang="scss" scoped>
.el-dialog {
  :deep(.el-dialog__header) {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 16px 16px 0 0;
    padding: 20px 24px;

    .el-dialog__title {
      font-weight: 600;
      font-size: 18px;
      color: white;
    }
  }

  :deep(.el-dialog__body) {
    padding: 24px;
  }
}

.preview-content {
  .preview-header {
    margin-bottom: 24px;

    .el-descriptions {
      :deep(.el-descriptions__header) {
        background: #f8fafc;
      }

      :deep(.el-descriptions__body) {
        .el-descriptions__table {
          border-radius: 8px;
          overflow: hidden;
        }
      }
    }
  }

  .preview-table {
    margin-bottom: 24px;

    .el-table {
      border-radius: 8px;
      overflow: hidden;

      :deep(.el-table__header) {
        background: #f8fafc;
      }
    }
  }

  .preview-pagination {
    display: flex;
    justify-content: center;

    .el-pagination {
      :deep(.el-pager) {
        li {
          border-radius: 6px;
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
</style>
