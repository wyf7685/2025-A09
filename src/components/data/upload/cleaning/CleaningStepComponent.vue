<script setup lang="ts">
import type { CleaningAction, CleaningStep, CleaningSuggestion } from '@/types/cleaning';
import { ElAlert, ElButton, ElEmpty } from 'element-plus';
import CleaningSuggestionItem from './CleaningSuggestionItem.vue';

// 当前步骤的双向绑定
const step = defineModel<CleaningStep>('step', {
  required: true,
  default: 'cleaning'
});

// 定义组件属性
const props = defineProps<{
  cleaningSuggestions: CleaningSuggestion[];
  selectedCleaningActions: CleaningAction[];
  isCleaning: boolean;
}>();

// 定义组件事件
const emit = defineEmits<{
  applyCleaningActions: [];
  skipAndUpload: [];
  toggleCleaningAction: [suggestion: CleaningSuggestion];
}>();

// 检查清洗动作是否已选择
const isCleaningActionSelected = (suggestion: CleaningSuggestion) => {
  // 组建议：当所有列都已选择时视为选中
  if (suggestion.columns && suggestion.columns.length > 0) {
    return suggestion.columns.every(col =>
      props.selectedCleaningActions.some(a => a.type === suggestion.type && a.column === col)
    );
  }
  return props.selectedCleaningActions.some(a =>
    a.type === suggestion.type && a.column === suggestion.column
  );
};

// 切换清洗动作选择
const toggleCleaningAction = (suggestion: CleaningSuggestion) => {
  emit('toggleCleaningAction', suggestion);
};

// 应用清洗操作
const applyCleaningActions = () => emit('applyCleaningActions');

// 跳过清洗直接上传
const skipAnalysisAndUpload = () => emit('skipAndUpload');
</script>

<template>
  <div class="cleaning-suggestions">
    <div v-if="isCleaning" class="cleaning-progress">
      <el-empty description="正在记录您的清洗选择，请稍候...">
        <template #image>
          <i-line-md-loading-loop width="60" height="60" color="#667eea" />
        </template>
      </el-empty>
    </div>
    <div v-else>
      <div class="suggestions-header">
        <div class="header-content">
          <div class="title">选择数据清洗建议</div>
          <div class="subtitle">
            根据数据质量分析结果，我们为您提供了以下清洗建议。请选择您认为合适的建议，系统将自动执行这些清洗操作。
          </div>
        </div>

        <el-alert title="功能说明" description="本系统将根据您选择的建议自动执行数据清洗操作，包括字段重命名、缺失值处理、异常值处理等，清洗后的数据将保存到Dremio中。" type="info"
          :closable="false">
          <template #icon>
            <i-material-symbols-info-outline width="20" height="20" color="#409EFF" />
          </template>
        </el-alert>
      </div>

      <div class="suggestions-actions">
        <div class="action-info">
          已选择 {{ selectedCleaningActions.length }} 个建议，共 {{ cleaningSuggestions.length }} 个建议
        </div>
        <div class="action-buttons">
          <el-button type="primary" @click="applyCleaningActions" :loading="isCleaning"
            :disabled="selectedCleaningActions.length === 0" size="large">
            <i-material-symbols-play-arrow-rounded width="18" height="18" style="margin-right: 4px;" />
            执行选中的清洗操作 ({{ selectedCleaningActions.length }})
          </el-button>

          <el-button @click="skipAnalysisAndUpload" size="large">
            <i-material-symbols-upload-rounded width="18" height="18" style="margin-right: 4px;" />
            跳过清洗直接上传
          </el-button>

          <el-button @click="step = 'analysis'" size="large">
            <i-material-symbols-arrow-back-rounded width="18" height="18" style="margin-right: 4px;" />
            返回分析结果
          </el-button>
        </div>
      </div>

      <div class="suggestions-list">
        <CleaningSuggestionItem v-for="(suggestion, index) in cleaningSuggestions" :key="index" :suggestion="suggestion"
          :isSelected="isCleaningActionSelected(suggestion)" @toggle="toggleCleaningAction" />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.cleaning-suggestions {
  .cleaning-progress {
    padding: 40px 0;
    text-align: center;
  }

  .suggestions-header {
    margin-bottom: 24px;

    .header-content {
      margin-bottom: 16px;

      .title {
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 8px;
      }

      .subtitle {
        font-size: 14px;
        color: #6b7280;
      }
    }
  }

  .suggestions-actions {
    background: #f9fafb;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 24px;
    border: 1px solid #e5e7eb;

    .action-info {
      font-size: 14px;
      color: #6b7280;
      margin-bottom: 12px;
      text-align: center;
    }

    .action-buttons {
      display: flex;
      gap: 12px;
      justify-content: center;
      flex-wrap: wrap;

      .el-button {
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
      }
    }
  }

  .suggestions-list {
    max-height: 500px;
    overflow-y: auto;
    padding-right: 8px;
  }
}
</style>
