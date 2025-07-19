<script setup lang="ts">
import type { CleaningAction, CleaningStep, CleaningSuggestion, DataQualityReport } from '@/types/cleaning';
import { computed } from 'vue';
import AnalysisStepComponent from './cleaning/AnalysisStepComponent.vue';
import CleaningStepComponent from './cleaning/CleaningStepComponent.vue';
import CleaningStepIndicator from './cleaning/CleaningStepIndicator.vue';
import CompleteStepComponent from './cleaning/CompleteStepComponent.vue';
import UploadStepComponent from './cleaning/UploadStepComponent.vue';

// 使用 defineModel 实现对话框可见性双向绑定
const visible = defineModel<boolean>('visible', { required: true });

// 当前清洗步骤
const step = defineModel<CleaningStep>('step', {
  required: true,
  default: 'upload'
});

// 用户要求和模型选择的双向绑定
const userRequirements = defineModel<string>('userRequirements', { default: '' });
const selectedModel = defineModel<string>('selectedModel', { default: '' });
const fileMetadata = defineModel<{ name: string, description: string; }>('fileMetadata', { required: true });

// 定义组件属性
defineProps<{
  file: File | null;
  dataQualityReport: DataQualityReport | null;
  cleaningSuggestions: CleaningSuggestion[];
  fieldMappings: Record<string, string>;
  isAnalyzing: boolean;
  isCleaning: boolean;
  selectedCleaningActions: CleaningAction[];
  analysisResult: any;
  availableModels: Array<{ value: string, label: string; }>;
}>();

// 定义组件事件
const emit = defineEmits<{
  analyze: [];
  skipAndUpload: [];
  applyCleaningActions: [];
  complete: [];
  close: [];
  toggleCleaningAction: [suggestion: CleaningSuggestion];
}>();

// 根据不同步骤返回不同宽度
const dialogWidth = computed(() => {
  switch (step.value) {
    case 'upload':
      return '600px';
    case 'analysis':
      return '55%';
    case 'cleaning':
      return '70%';
    case 'complete':
      return '700px';
    default:
      return '60%';
  }
});

// 关闭对话框
const closeDialog = () => {
  emit('close');
};
</script>

<template>
  <el-dialog v-model="visible" title="数据清洗与分析" :width="dialogWidth" :before-close="closeDialog">
    <div class="cleaning-content">
      <!-- 步骤指示器 -->
      <CleaningStepIndicator :currentStep="step" />

      <!-- 上传文件信息 -->
      <UploadStepComponent v-if="step === 'upload'" v-model:fileMetadata="fileMetadata"
        v-model:userRequirements="userRequirements" v-model:selectedModel="selectedModel" :file="file"
        :isAnalyzing="isAnalyzing" :availableModels="availableModels" @analyze="emit('analyze')"
        @skipAndUpload="emit('skipAndUpload')" @close="emit('close')" />

      <!-- 数据质量分析结果 -->
      <AnalysisStepComponent v-if="step === 'analysis'" v-model:step="step" :dataQualityReport="dataQualityReport"
        :cleaningSuggestions="cleaningSuggestions" :fieldMappings="fieldMappings" :isAnalyzing="isAnalyzing"
        :analysisResult="analysisResult" @skipAndUpload="emit('skipAndUpload')" />

      <!-- 清洗建议选择 -->
      <CleaningStepComponent v-if="step === 'cleaning'" v-model:step="step" :cleaningSuggestions="cleaningSuggestions"
        :selectedCleaningActions="selectedCleaningActions" :isCleaning="isCleaning"
        @applyCleaningActions="emit('applyCleaningActions')" @skipAndUpload="emit('skipAndUpload')"
        @toggleCleaningAction="emit('toggleCleaningAction', $event)" />

      <!-- 完成状态 -->
      <CompleteStepComponent v-if="step === 'complete'" v-model:step="step" :analysisResult="analysisResult"
        :selectedCleaningActions="selectedCleaningActions" :cleaningSuggestions="cleaningSuggestions"
        @complete="emit('complete')" @skipAndUpload="emit('skipAndUpload')" @analyze="emit('analyze')" />
    </div>
  </el-dialog>
</template>

<style lang="scss" scoped>
.cleaning-content {
  padding: 20px;
}

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
    padding: 0;
  }
}
</style>
