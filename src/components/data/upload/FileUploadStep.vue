<script setup lang="ts">
import AnalysisStepComponent from './cleaning/AnalysisStepComponent.vue';
import CleaningStepComponent from './cleaning/CleaningStepComponent.vue';
import CleaningStepIndicator from './cleaning/CleaningStepIndicator.vue';
import CompleteStepComponent from './cleaning/CompleteStepComponent.vue';
import UploadStepComponent from './cleaning/UploadStepComponent.vue';
import type { AnalyzeDataQualityState, CleaningAction, CleaningStep, CleaningSuggestion, DataQualityReport } from '@/types/cleaning';
import { cleaningAPI } from '@/utils/api';
import { withLoading } from '@/utils/tools';
import { ArrowLeft } from '@element-plus/icons-vue';
import { ElButton, ElIcon, ElMessage } from 'element-plus';
import { ref } from 'vue';

// 文件元数据模型
const fileName = defineModel<string>('fileName', { required: true });
const fileDescription = defineModel<string>('fileDescription', { default: '' });
const userRequirements = defineModel<string>('userRequirements', { default: '' });
const selectedModel = defineModel<string>('selectedModel', { default: '' });
const selectedFile = defineModel<File | null>('selectedFile', { required: true });

// 定义属性
defineProps<{
  availableModels: { value: string; label: string; }[];
}>();

// 定义事件
const emit = defineEmits<{
  goBack: [];
  proceed: [cleanedFileId?: string];
}>();


// 清洗流程相关状态
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

  // 调用 API 获取数据质量报告
  const result = await cleaningAPI.analyzeDataQuality(
    selectedFile.value,
    userRequirements.value,
  );

  analysisResult.value = result as AnalyzeDataQualityState;
  dataQualityReport.value = result.quality_report;
  cleaningSuggestions.value = result.cleaning_suggestions;
  fieldMappings.value = result.field_mappings;
  cleanedFileId.value = result.cleaned_file_id || undefined;

  // 进入下一步
  currentStep.value = 'analysis';
}, '数据分析失败');

// 跳过清洗直接上传
const skipAndUpload = () => {
  emit('proceed', cleanedFileId.value);
};

// 应用清洗操作
const applyCleaningActions = () => withLoading(isCleaning, async () => {
  if (!selectedFile.value) return;

  const result = await cleaningAPI.executeCleaning(
    selectedFile.value,
    cleaningSuggestions.value.filter(s =>
      selectedCleaningActions.value.some(a => a.column === s.column && a.type === s.type)
    ),
    fieldMappings.value,
    userRequirements.value,
    selectedModel.value || undefined
  );

  if (result.success) {
    // 保存清洗后文件ID
    cleanedFileId.value = result.cleaned_file_id;

    // 进入完成步骤
    currentStep.value = 'complete';
  } else {
    ElMessage.error(result.error || '数据清洗失败');
  }
}, '数据清洗失败');

// 切换清洗操作
const toggleCleaningAction = (suggestion: CleaningSuggestion) => {
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
