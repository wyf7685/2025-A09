<script setup lang="ts">
import AnalysisStepComponent from '@/components/data/cleaning/AnalysisStepComponent.vue';
import CleaningStepComponent from '@/components/data/cleaning/CleaningStepComponent.vue';
import CleaningStepIndicator from '@/components/data/cleaning/CleaningStepIndicator.vue';
import CompleteStepComponent from '@/components/data/cleaning/CompleteStepComponent.vue';
import UploadStepComponent from '@/components/data/cleaning/UploadStepComponent.vue';
import type { CleaningAction, CleaningStep, CleaningSuggestion, DataQualityReport } from '@/types/cleaning';
import { cleaningAPI } from '@/utils/api';
import { ArrowLeft } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, ref } from 'vue';

// 文件元数据模型
const fileName = defineModel<string>('fileName', { required: true });
const fileDescription = defineModel<string>('fileDescription', { default: '' });
const userRequirements = defineModel<string>('userRequirements', { default: '' });
const selectedModel = defineModel<string>('selectedModel', { default: '' });
const selectedFile = defineModel<File | null>('selectedFile', { required: true });

// 定义属性
const props = defineProps<{
  availableModels: Array<{ value: string; label: string; }>;
}>();

// 定义事件
const emit = defineEmits<{
  fileSelected: [file: File];
  goBack: [];
  proceed: [cleanedFileId?: string];
}>();

// 上传相关状态
const uploadRef = ref();
// const selectedFile = ref<File | null>(null);
const dragover = ref(false);

// 清洗流程相关状态
const currentStep = ref<CleaningStep>('upload');
const dataQualityReport = ref<DataQualityReport | null>(null);
const cleaningSuggestions = ref<CleaningSuggestion[]>([]);
const selectedCleaningActions = ref<CleaningAction[]>([]);
const fieldMappings = ref<Record<string, string>>({});
const analysisResult = ref<any>(null);
const isAnalyzing = ref(false);
const isCleaning = ref(false);
const cleanedFileId = ref<string | undefined>(undefined);

// 文件元数据对象（为了兼容原组件）
const fileMetadata = computed({
  get: () => ({
    name: fileName.value,
    description: fileDescription.value
  }),
  set: (val) => {
    fileName.value = val.name;
    fileDescription.value = val.description;
  }
});

// 处理文件上传
const handleFileUpload = (file: File) => {
  // 检查文件类型
  const allowedTypes = ['csv', 'xlsx', 'xls'];
  const fileExtension = file.name.split('.').pop()?.toLowerCase();

  if (!fileExtension || !allowedTypes.includes(fileExtension)) {
    ElMessage.error('只支持 CSV 和 Excel 文件格式');
    return false;
  }

  // 更新文件名（如果未设置）
  if (!fileName.value) {
    fileName.value = file.name.split('.')[0];
  }

  selectedFile.value = file;
  emit('fileSelected', file);

  return false; // 阻止 el-upload 默认上传行为
};

// 处理文件拖放
const handleDragover = () => {
  dragover.value = true;
};

const handleDragleave = () => {
  dragover.value = false;
};

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
const startAnalysis = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择一个文件');
    return;
  }

  if (!fileName.value) {
    ElMessage.warning('请输入文件名称');
    return;
  }

  isAnalyzing.value = true;

  try {
    // 调用 API 获取数据质量报告
    const result = await cleaningAPI.analyzeDataQuality(selectedFile.value, userRequirements.value);

    analysisResult.value = result;
    dataQualityReport.value = result.quality_report;
    cleaningSuggestions.value = result.cleaning_suggestions;
    fieldMappings.value = result.field_mappings;
    cleanedFileId.value = result.cleaned_file_id;

    // 进入下一步
    currentStep.value = 'analysis';
  } catch (error) {
    console.error('Data analysis failed:', error);
    ElMessage.error('数据分析失败');
  } finally {
    isAnalyzing.value = false;
  }
};

// 跳过清洗直接上传
const skipAndUpload = () => {
  emit('proceed', cleanedFileId.value);
};

// 应用清洗操作
const applyCleaningActions = async () => {
  if (!selectedFile.value) return;

  isCleaning.value = true;

  try {
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

      // 更新分析结果
      analysisResult.value = {
        ...analysisResult.value,
        cleaning_result: result
      };

      // 进入完成步骤
      currentStep.value = 'complete';
    } else {
      ElMessage.error(result.error || '数据清洗失败');
    }
  } catch (error) {
    console.error('Data cleaning failed:', error);
    ElMessage.error('数据清洗失败');
  } finally {
    isCleaning.value = false;
  }
};

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

const proceed = () => {
  // 初始上传步骤，开始分析
  if (currentStep.value === 'upload') {
    startAnalysis();
  } else {
    skipAndUpload();
  }
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

    <!-- 步骤指示器 (显示在除了初始上传步骤外的所有步骤) -->
    <CleaningStepIndicator :currentStep="currentStep" />

    <!-- 上传步骤 -->
    <!-- <div v-if="currentStep === 'upload'" class="step-container">
      <div class="upload-section">
        <h3>上传文件</h3>

        <el-upload ref="uploadRef" class="upload-area" drag action="#" :auto-upload="false" :show-file-list="false"
          :on-change="(file: { raw: File; }) => handleFileUpload(file.raw)" :multiple="false" @dragover="handleDragover"
          @dragleave="handleDragleave">
          <div class="upload-content" :class="{ 'active-drag': dragover }">
            <el-icon class="upload-icon">
              <UploadFilled />
            </el-icon>
            <div class="upload-text">
              <h4>拖拽文件到此处，或 <em>点击上传</em></h4>
              <p>支持 CSV、Excel (.xlsx, .xls) 文件</p>
            </div>
            <div v-if="selectedFile" class="selected-file">
              <p>已选择: {{ selectedFile.name }}</p>
            </div>
          </div>
        </el-upload>
      </div>

      <div class="metadata-section">
        <h3>文件信息</h3>

        <el-form label-position="top">
          <el-form-item label="名称" required>
            <el-input v-model="fileName" placeholder="请输入数据集名称" />
          </el-form-item>

          <el-form-item label="描述">
            <el-input v-model="fileDescription" type="textarea" :rows="3" placeholder="请输入数据集描述（可选）" />
          </el-form-item>

          <el-divider />

          <h3>数据处理设置</h3>
          <el-form-item label="数据处理需求">
            <el-input v-model="userRequirements" type="textarea" :rows="3"
              placeholder="请描述您对数据的处理需求，例如：清洗缺失值、标准化数值列、处理异常值等（可选）" />
          </el-form-item>

          <el-form-item label="使用模型">
            <el-select v-model="selectedModel" placeholder="请选择处理模型（可选）" style="width: 100%">
              <el-option v-for="model in availableModels" :key="model.value" :label="model.label"
                :value="model.value" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <div class="actions">
        <el-button @click="goBack">上一步</el-button>
        <el-button @click="skipAndUpload">跳过清洗并上传</el-button>
        <el-button type="primary" @click="proceed" :disabled="!selectedFile || !fileName" :loading="isAnalyzing">
          {{ isAnalyzing ? '分析中...' : '分析数据' }}
        </el-button>
      </div>
    </div> -->

    <UploadStepComponent v-if="currentStep === 'upload'" v-model:file-name="fileName"
      v-model:file-description="fileDescription" v-model:user-requirements="userRequirements"
      v-model:selected-model="selectedModel" v-model:file-metadata="fileMetadata" :selected-file="selectedFile"
      :is-analyzing="isAnalyzing" :available-models="availableModels" @analyze="startAnalysis"
      @skip-and-upload="skipAndUpload" @close="emit('goBack')" @file-selected="emit('fileSelected', $event)" />

    <!-- 分析步骤 -->
    <AnalysisStepComponent v-if="currentStep === 'analysis'" v-model:step="currentStep"
      :dataQualityReport="dataQualityReport" :cleaningSuggestions="cleaningSuggestions" :fieldMappings="fieldMappings"
      :isAnalyzing="isAnalyzing" :analysisResult="analysisResult" @skipAndUpload="skipAndUpload" />

    <!-- 清洗步骤 -->
    <CleaningStepComponent v-if="currentStep === 'cleaning'" v-model:step="currentStep"
      :cleaningSuggestions="cleaningSuggestions" :selectedCleaningActions="selectedCleaningActions"
      :isCleaning="isCleaning" @applyCleaningActions="applyCleaningActions" @skipAndUpload="skipAndUpload"
      @toggleCleaningAction="toggleCleaningAction" />

    <!-- 完成步骤 -->
    <CompleteStepComponent v-if="currentStep === 'complete'" v-model:step="currentStep" :analysisResult="analysisResult"
      :selectedCleaningActions="selectedCleaningActions" :cleaningSuggestions="cleaningSuggestions"
      @complete="completeCleaning" @skipAndUpload="skipAndUpload" @analyze="startAnalysis" />
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
