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
    <!-- 移除图标块，避免空方块显示 -->
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
          <template v-if="suggestion.columns && suggestion.columns.length > 0">
            <div class="columns-list">
              <el-tag v-for="col in suggestion.columns" :key="col" type="info" size="small">{{ col }}</el-tag>
            </div>
          </template>
          <template v-else>
            <el-tag type="info" size="small">{{ suggestion.column }}</el-tag>
          </template>
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

  /* 移除 .item-icon 样式块 */

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

        .columns-list {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }
      }
    }
  }

  .item-action {
    margin-top: 4px;
  }
}
</style>
