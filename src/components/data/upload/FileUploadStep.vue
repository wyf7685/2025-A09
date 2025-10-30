<script setup lang="ts">
import type { AnalyzeDataQualityState, CleaningAction, CleaningStep, CleaningSuggestion, DataQualityReport } from '@/types/cleaning';
import { ArrowDown, ArrowLeft, ArrowRight } from '@element-plus/icons-vue';
import { ElButton, ElMessage } from 'element-plus';
import { ref } from 'vue';
import { Icon } from '@iconify/vue';
import UploadStepComponent from './cleaning/UploadStepComponent.vue';
import AnalysisStepComponent from './cleaning/AnalysisStepComponent.vue';
import CleaningStepComponent from './cleaning/CleaningStepComponent.vue';
import CompleteStepComponent from './cleaning/CompleteStepComponent.vue';
import { cleaningAPI } from '@/utils/api';

import CleaningStepIndicator from './cleaning/CleaningStepIndicator.vue';
import { withLoading } from '@/utils/tools';
import type { LLMModel } from '@/types';

// 事件定义
const emit = defineEmits<{
  goBack: [];
  proceed: [cleanedFileId?: string];
}>();

// v-model 双向绑定定义（从父视图 DataUpload.vue 传入）
const fileName = defineModel<string>('fileName', { required: true });
const fileDescription = defineModel<string>('fileDescription', { required: true });
const userRequirements = defineModel<string>('userRequirements', { required: true });
const selectedModel = defineModel<string>('selectedModel', { required: true });
const selectedFile = defineModel<File | null>('selectedFile', { required: true });

// 组件属性（可用模型列表）
const { availableModels } = defineProps<{ availableModels: LLMModel[] }>();

const currentStep = ref<CleaningStep>('upload');
const dataQualityReport = ref<DataQualityReport | null>(null);
const cleaningSuggestions = ref<CleaningSuggestion[]>([]);
const selectedCleaningActions = ref<CleaningAction[]>([]);
const fieldMappings = ref<Record<string, string>>({});
const analysisResult = ref<AnalyzeDataQualityState | null>(null);
const isAnalyzing = ref(false);
const isCleaning = ref(false);
const cleanedFileId = ref<string | undefined>(undefined);

const goBack = () => {
  if (currentStep.value === 'upload') {
    emit('goBack');
  } else {
    // 返回上一步清洗流程
    switch (currentStep.value) {
      case 'analysis':
        currentStep.value = 'upload';
        break;
      case 'cleaning':
        currentStep.value = 'analysis';
        break;
      case 'complete':
        currentStep.value = 'cleaning';
        break;
    }
  }
};

// 开始数据分析
const startAnalysis = () => withLoading(isAnalyzing, async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择一个文件');
    return;
  }

  if (!fileName.value) {
    ElMessage.warning('请输入文件名称');
    return;
  }

  if (!selectedModel.value) {
    ElMessage.warning('请选择一个模型');
    return;
  }

  // 先切换到分析视图，显示加载状态
  currentStep.value = 'analysis';
  analysisResult.value = null;
  dataQualityReport.value = null;
  cleaningSuggestions.value = [];
  fieldMappings.value = {};

  // 调用 API 获取数据质量报告
  const result = await cleaningAPI.analyzeDataQuality(
    selectedFile.value,
    userRequirements.value,
    selectedModel.value || undefined,
  );

  analysisResult.value = result as AnalyzeDataQualityState;
  dataQualityReport.value = result.quality_report;
  cleaningSuggestions.value = result.cleaning_suggestions;
  fieldMappings.value = result.field_mappings;
  cleanedFileId.value = result.cleaned_file_id || undefined;
}, '数据分析失败');

// 跳过清洗直接上传
const skipAndUpload = () => {
  emit('proceed', cleanedFileId.value);
};

// 应用清洗操作
const applyCleaningActions = () => withLoading(isCleaning, async () => {
  if (!selectedFile.value) return;

  // 将组建议展开为逐列建议以便后端执行
  const expandedSuggestions: CleaningSuggestion[] = cleaningSuggestions.value.flatMap(s => {
    if (s.columns && s.columns.length > 0) {
      return s.columns.map(col => ({ ...s, column: col, columns: undefined }));
    }
    return [s];
  });

  // 根据选中项执行清洗逻辑，仅执行用户选择的动作
  const actionsToApply: CleaningAction[] = selectedCleaningActions.value.map(a => ({ ...a }));

  // 如果没有用户选择，则默认执行所有建议
  const suggestionsToApply = actionsToApply.length > 0
    ? expandedSuggestions.filter(s => actionsToApply.some(a => a.type === s.type && a.column === s.column))
    : expandedSuggestions;

  const result = await cleaningAPI.executeCleaning(
    selectedFile.value,
    suggestionsToApply,
    fieldMappings.value,
    userRequirements.value,
    selectedModel.value || undefined,
  );

  if (result.success) {
    cleanedFileId.value = result.cleaned_file_id || cleanedFileId.value;
    currentStep.value = 'complete';
  } else {
    ElMessage.error(result.error || '数据清洗失败');
  }
}, '执行清洗操作失败');

// 切换清洗动作选择
const toggleCleaningAction = (suggestion: CleaningSuggestion) => {
  // 组建议：批量勾选/取消所有列
  if (suggestion.columns && suggestion.columns.length > 0) {
    const allSelected = suggestion.columns.every(col =>
      selectedCleaningActions.value.some(a => a.type === suggestion.type && a.column === col)
    );

    if (allSelected) {
      // 取消所有列
      suggestion.columns.forEach(col => {
        const idx = selectedCleaningActions.value.findIndex(a => a.type === suggestion.type && a.column === col);
        if (idx >= 0) selectedCleaningActions.value.splice(idx, 1);
      });
    } else {
      // 勾选所有列（去重）
      suggestion.columns.forEach(col => {
        const exists = selectedCleaningActions.value.some(a => a.type === suggestion.type && a.column === col);
        if (!exists) {
          selectedCleaningActions.value.push({ type: suggestion.type, column: col });
        }
      });
    }
    return;
  }

  const existingIndex = selectedCleaningActions.value.findIndex(
    action => action.column === suggestion.column && action.type === suggestion.type
  );

  if (existingIndex >= 0) {
    // 取消选择
    selectedCleaningActions.value.splice(existingIndex, 1);
  } else {
    // 添加选择
    selectedCleaningActions.value.push({
      type: suggestion.type,
      column: suggestion.column
    });
  }
};

// 完成清洗流程
const completeCleaning = () => {
  emit('proceed', cleanedFileId.value);
};
</script>

<template>
  <div class="file-upload-step">
    <div class="back-button">
      <el-button @click="goBack" text>
        <el-icon>
          <ArrowLeft />
        </el-icon>
        返回
      </el-button>
    </div>

    <!-- 步骤指示器 -->
    <CleaningStepIndicator :currentStep="currentStep" />

    <UploadStepComponent v-if="currentStep === 'upload'"
      v-model:file-name="fileName"
      v-model:file-description="fileDescription"
      v-model:user-requirements="userRequirements"
      v-model:selected-model="selectedModel"
      v-model:selected-file="selectedFile"
      :is-analyzing="isAnalyzing"
      :available-models="availableModels"
      @analyze="startAnalysis"
      @skip-and-upload="skipAndUpload"
      @close="emit('goBack')" />

    <!-- 分析步骤 -->
    <AnalysisStepComponent v-if="currentStep === 'analysis'"
      :dataQualityReport="dataQualityReport"
      :cleaningSuggestions="cleaningSuggestions"
      :fieldMappings="fieldMappings"
      :isAnalyzing="isAnalyzing"
      :analysisResult="analysisResult"
      @skip-and-upload="skipAndUpload"
      @goto-cleaning="currentStep = 'cleaning'"
      @goto-upload="currentStep = 'upload'" />

    <!-- 清洗步骤 -->
    <CleaningStepComponent v-if="currentStep === 'cleaning'"
      v-model:step="currentStep"
      :cleaning-suggestions="cleaningSuggestions"
      :selected-cleaning-actions="selectedCleaningActions"
      :is-cleaning="isCleaning"
      @apply-cleaning-actions="applyCleaningActions"
      @skip-and-upload="skipAndUpload"
      @toggle-cleaning-action="toggleCleaningAction" />

    <!-- 完成步骤 -->
    <CompleteStepComponent v-if="currentStep === 'complete'"
      v-model:step="currentStep"
      :analysis-result="analysisResult"
      :selected-cleaning-actions="selectedCleaningActions"
      :cleaning-suggestions="cleaningSuggestions"
      :cleaned-file-id="cleanedFileId"
      @complete="completeCleaning"
      @skip-and-upload="skipAndUpload"
      @analyze="startAnalysis" />
  </div>
</template>

<style lang="scss" scoped>
.file-upload-step {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 20px 40px;

  .back-button {
    margin-bottom: 20px;
  }

  h3 {
    font-size: 18px;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 16px;
  }

  .step-container {
    margin-top: 30px;
  }

  .metadata-section {
    margin-top: 30px;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 30px;
    gap: 12px;
  }
}
</style>
