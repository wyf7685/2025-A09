<script setup lang="ts">
import type { CleaningAction, CleaningStep, CleaningSuggestion } from '@/types/cleaning';
import { CircleCheck, EditPen, RefreshRight, Upload } from '@element-plus/icons-vue';

// 当前步骤的双向绑定
const step = defineModel<CleaningStep>('step', {
  required: true,
  default: 'complete'
});

// 定义组件属性
defineProps<{
  analysisResult: any;
  selectedCleaningActions: CleaningAction[];
  cleaningSuggestions: CleaningSuggestion[];
}>();

// 定义组件事件
const emit = defineEmits<{
  complete: [];
  skipAndUpload: [];
  analyze: [];
}>();

// 完成清洗
const completeCleaningAndUpload = () => emit('complete');

// 跳过清洗直接上传
const skipAnalysisAndUpload = () => emit('skipAndUpload');

// 重新分析
const startAnalysis = () => emit('analyze');
</script>

<template>
  <div class="complete-status">
    <el-result status="success" title="处理完成" :sub-title="analysisResult?.data_uploaded ?
      '数据已成功上传到Dremio，您可以在数据源列表中查看' :
      '数据处理完成，请选择操作'">
      <template #extra>
        <div class="complete-actions">
          <el-button type="primary" @click="completeCleaningAndUpload" size="large"
            v-if="analysisResult?.data_uploaded">
            <el-icon>
              <CircleCheck />
            </el-icon>
            关闭并查看数据源列表
          </el-button>

          <el-button type="primary" @click="skipAnalysisAndUpload" size="large" v-if="!analysisResult?.data_uploaded">
            <el-icon>
              <Upload />
            </el-icon>
            立即上传数据
          </el-button>

          <el-button @click="startAnalysis" size="large">
            <el-icon>
              <RefreshRight />
            </el-icon>
            重新分析数据质量
          </el-button>

          <el-button @click="step = 'cleaning'" v-if="cleaningSuggestions.length > 0 && !analysisResult?.data_uploaded"
            size="large">
            <el-icon>
              <EditPen />
            </el-icon>
            重新选择清洗操作
          </el-button>
        </div>

        <div class="complete-summary" v-if="selectedCleaningActions.length > 0">
          <el-card class="summary-card">
            <template #header>
              <span>已执行的清洗操作摘要</span>
            </template>
            <div class="summary-list">
              <div v-for="(action, index) in selectedCleaningActions" :key="index" class="summary-item">
                <el-tag type="primary" size="small">{{ action.type }}</el-tag>
                <span>{{ action.column }}</span>
              </div>
            </div>
          </el-card>
        </div>
      </template>
    </el-result>
  </div>
</template>

<style lang="scss" scoped>
.complete-status {
  .complete-actions {
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 24px;

    .el-button {
      border-radius: 8px;
      padding: 12px 24px;
      font-weight: 500;
    }
  }

  .complete-summary {
    max-width: 500px;
    margin: 0 auto;

    .summary-card {
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);

      :deep(.el-card__header) {
        background: #f9fafb;
        font-weight: 600;
        color: #1f2937;
      }

      .summary-list {
        .summary-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 8px 0;
          border-bottom: 1px solid #e5e7eb;

          &:last-child {
            border-bottom: none;
          }

          .el-tag {
            border-radius: 4px;
          }

          span {
            font-size: 14px;
            color: #374151;
          }
        }
      }
    }
  }
}
</style>
