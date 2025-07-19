<script setup lang="ts">
import type { DataSourceMetadataWithID } from '@/types';
import { formatRowCount } from '@/utils/dataSourceUtils';
import {
  Connection,
  Delete,
  Document,
  DocumentCopy,
  Download,
  Edit,
  Folder,
  More,
  TrendCharts,
  View
} from '@element-plus/icons-vue';

interface Props {
  dataSource: DataSourceMetadataWithID;
}

interface Emits {
  (e: 'analyze', dataSource: DataSourceMetadataWithID): void;
  (e: 'preview', dataSource: DataSourceMetadataWithID): void;
  (e: 'edit', dataSource: DataSourceMetadataWithID): void;
  (e: 'download', dataSource: DataSourceMetadataWithID): void;
  (e: 'delete', dataSource: DataSourceMetadataWithID): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// 获取图标组件
const getIconComponent = () => {
  const type = props.dataSource.source_type.toLowerCase();
  if (type.includes('csv')) return DocumentCopy;
  if (type.includes('excel') || type.includes('xlsx')) return Document;
  if (type.includes('database') || type.includes('direct')) return Connection;
  return Folder;
};

// 获取类型标签颜色
const getTypeTagType = () => {
  const type = props.dataSource.source_type.toLowerCase();
  if (type.includes('csv')) return 'success';
  if (type.includes('excel')) return 'warning';
  if (type.includes('database')) return 'danger';
  return 'info';
};

// 获取类型文本
const getTypeText = () => {
  const type = props.dataSource.source_type;
  if (type.includes('csv')) return 'CSV';
  if (type.includes('excel')) return 'Excel';
  if (type.includes('database')) return '数据库';
  return '未知';
};

// 获取状态标签颜色
const getStatusTagType = () => {
  if (props.dataSource.row_count && props.dataSource.row_count > 0) {
    return 'success';
  }
  if (props.dataSource.row_count === 0) {
    return 'warning';
  }
  return 'info';
};

// 获取状态文本
const getStatusText = () => {
  if (props.dataSource.row_count && props.dataSource.row_count > 0) {
    return '正常';
  }
  if (props.dataSource.row_count === 0) {
    return '无数据';
  }
  return '未知';
};
</script>

<template>
  <div class="data-source-card">
    <div class="card-header">
      <div class="card-title">
        <el-icon class="title-icon">
          <component :is="getIconComponent()" />
        </el-icon>
        <span class="title-text">{{ dataSource.name }}</span>
      </div>
      <div class="card-status">
        <el-tag :type="getStatusTagType()" size="small" round>
          {{ getStatusText() }}
        </el-tag>
      </div>
    </div>

    <div class="card-content">
      <div class="card-description">
        {{ dataSource.description || '暂无描述' }}
      </div>

      <div class="card-stats">
        <div class="stat-item">
          <span class="stat-label">类型</span>
          <el-tag size="small" :type="getTypeTagType()">
            {{ getTypeText() }}
          </el-tag>
        </div>
        <div class="stat-item">
          <span class="stat-label">数据量</span>
          <span class="stat-value">{{ formatRowCount(dataSource.row_count) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">列数</span>
          <span class="stat-value">{{ dataSource.column_count || 'N/A' }}</span>
        </div>
      </div>
    </div>

    <div class="card-actions">
      <el-button size="small" type="primary" @click="$emit('analyze', dataSource)" :icon="TrendCharts">
        分析
      </el-button>
      <el-button size="small" type="success" @click="$emit('preview', dataSource)" :icon="View">
        预览
      </el-button>
      <el-dropdown trigger="click">
        <el-button size="small" type="info" :icon="More">
          更多
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="$emit('edit', dataSource)">
              <el-icon>
                <Edit />
              </el-icon>
              编辑信息
            </el-dropdown-item>
            <el-dropdown-item @click="$emit('download', dataSource)">
              <el-icon>
                <Download />
              </el-icon>
              导出数据
            </el-dropdown-item>
            <el-dropdown-item @click="$emit('delete', dataSource)" style="color: #f56565">
              <el-icon>
                <Delete />
              </el-icon>
              删除
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.data-source-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  transition: all 0.3s ease;
  border: 1px solid #e5e7eb;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    border-color: #667eea;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  border-bottom: 1px solid #e5e7eb;

  .card-title {
    display: flex;
    align-items: center;
    gap: 8px;

    .title-icon {
      color: #667eea;
      font-size: 20px;
    }

    .title-text {
      font-weight: 600;
      color: #1f2937;
      font-size: 16px;
    }
  }

  .card-status {
    .el-tag {
      font-weight: 500;
    }
  }
}

.card-content {
  padding: 16px 20px;

  .card-description {
    color: #6b7280;
    font-size: 14px;
    margin-bottom: 16px;
    line-height: 1.5;
  }

  .card-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
    gap: 12px;

    .stat-item {
      text-align: center;

      .stat-label {
        display: block;
        font-size: 12px;
        color: #9ca3af;
        margin-bottom: 4px;
      }

      .stat-value {
        font-weight: 600;
        color: #374151;
        font-size: 14px;
      }
    }
  }
}

.card-actions {
  display: flex;
  gap: 8px;
  padding: 16px 20px;
  background: #f9fafb;
  border-top: 1px solid #e5e7eb;

  .el-button {
    border-radius: 6px;
    font-weight: 500;

    &:first-child {
      flex: 1;
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .card-content {
    .card-stats {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .card-actions {
    flex-direction: column;
    gap: 8px;

    .el-button {
      width: 100%;
    }
  }
}
</style>
