<script setup lang="ts">
import type { CleaningSuggestion } from '@/types/cleaning';
import {
  CircleClose,
  DocumentChecked,
  DocumentCopy, Edit, InfoFilled,
  QuestionFilled, Warning
} from '@element-plus/icons-vue';
import { ElButton, ElCheckbox, ElIcon, ElTag } from 'element-plus';

// 定义组件属性
const props = defineProps<{
  suggestion: CleaningSuggestion;
  isSelected: boolean;
}
>();

// 定义组件事件
const emit = defineEmits<{
  toggle: [suggestion: CleaningSuggestion];
}>();

// 获取问题类型的图标
const getIssueTypeIcon = (type: string) => {
  switch (type) {
    case 'missing_values':
      return QuestionFilled;
    case 'outliers':
      return Warning;
    case 'duplicates':
    case 'duplicate_rows':
      return DocumentCopy;
    case 'invalid_values':
      return CircleClose;
    case 'column_name':
      return Edit;
    case 'data_type':
      return DocumentChecked;
    default:
      return InfoFilled;
  }
};

// 获取问题类型的颜色
const getIssueTypeColor = (type: string) => {
  switch (type) {
    case 'missing_values':
      return 'warning';
    case 'outliers':
      return 'danger';
    case 'duplicates':
    case 'duplicate_rows':
      return 'info';
    case 'invalid_values':
      return 'danger';
    case 'column_name':
      return 'primary';
    case 'data_type':
      return 'success';
    default:
      return 'info';
  }
};

// 获取优先级颜色
const getPriorityColor = (priority: string) => {
  switch (priority) {
    case 'high':
      return 'danger';
    case 'medium':
      return 'warning';
    case 'low':
      return 'success';
    default:
      return 'info';
  }
};

// 切换选择状态
const toggleSelection = () => {
  emit('toggle', props.suggestion);
};
</script>

<template>
  <div class="suggestion-item">
    <div class="item-checkbox">
      <el-checkbox :checked="isSelected" @change="toggleSelection" size="large" />
    </div>
    <div class="item-icon" :class="`icon-${getIssueTypeColor(suggestion.type)}`">
      <el-icon :component="getIssueTypeIcon(suggestion.type)" />
    </div>
    <div class="item-content">
      <div class="item-header">
        <div class="item-title">{{ suggestion.description }}</div>
        <div class="item-badges">
          <el-tag :type="getIssueTypeColor(suggestion.type)" size="small">
            {{ suggestion.type }}
          </el-tag>
          <el-tag :type="getPriorityColor(suggestion.priority || 'medium')" size="small">
            {{ suggestion.priority || 'medium' }} 优先级
          </el-tag>
        </div>
      </div>
      <div class="item-details">
        <div class="detail-row">
          <span class="detail-label">影响列:</span>
          <el-tag type="info" size="small">{{ suggestion.column }}</el-tag>
        </div>
        <div class="detail-row" v-if="suggestion.impact">
          <span class="detail-label">影响程度:</span>
          <span class="detail-value">{{ suggestion.impact }}</span>
        </div>
        <div class="detail-row" v-if="suggestion.reason">
          <span class="detail-label">建议原因:</span>
          <span class="detail-value">{{ suggestion.reason }}</span>
        </div>
      </div>
    </div>
    <div class="item-action">
      <el-button :type="isSelected ? 'success' : 'default'" size="small" @click="toggleSelection">
        {{ isSelected ? '已选择' : '选择' }}
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  margin-bottom: 16px;
  transition: all 0.2s ease;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .item-checkbox {
    margin-top: 4px;
  }

  .item-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    margin-top: 4px;

    &.icon-success {
      background: #f0fdf4;
      color: #22c55e;
    }

    &.icon-warning {
      background: #fef3c7;
      color: #f59e0b;
    }

    &.icon-danger {
      background: #fef2f2;
      color: #ef4444;
    }

    &.icon-info {
      background: #eff6ff;
      color: #3b82f6;
    }

    &.icon-primary {
      background: #f3f4f6;
      color: #6366f1;
    }
  }

  .item-content {
    flex: 1;

    .item-header {
      margin-bottom: 12px;

      .item-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 8px;
      }

      .item-badges {
        display: flex;
        gap: 8px;
      }
    }

    .item-details {
      .detail-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        &:last-child {
          margin-bottom: 0;
        }

        .detail-label {
          font-size: 14px;
          color: #6b7280;
          font-weight: 500;
          min-width: 80px;
        }

        .detail-value {
          font-size: 14px;
          color: #374151;
        }
      }
    }
  }

  .item-action {
    margin-top: 4px;
  }
}
</style>
