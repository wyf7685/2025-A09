<script setup lang="ts">
import { ArrowDown, ArrowRight, DataAnalysis, Document, InfoFilled, Upload, UploadFilled } from '@element-plus/icons-vue';
import { ElButton, ElCol, ElCollapseTransition, ElForm, ElFormItem, ElIcon, ElInput, ElMessage, ElOption, ElRow, ElSelect, ElUpload, type UploadFile } from 'element-plus';
import { Icon } from '@iconify/vue';
import { ref } from 'vue';

// 双向绑定数据
const fileName = defineModel<string>('fileName', { required: true });
const fileDescription = defineModel<string>('fileDescription', { required: true });
const userRequirements = defineModel<string>('userRequirements', { required: true });
const selectedModel = defineModel<string>('selectedModel', { required: true });
const selectedFile = defineModel<File | null>('selectedFile', { required: true });

// 定义组件属性
defineProps<{
  isAnalyzing: boolean;
  availableModels: Array<{ value: string, label: string; }>;
}>();

// 定义组件事件
const emit = defineEmits<{
  analyze: [];
  skipAndUpload: [];
  close: [];
}>();

// 文件上传相关状态
const dragover = ref(false);

// 高级选项显示状态
const showAdvancedOptions = ref(false);

// 处理函数
const startAnalysis = () => emit('analyze');
const skipAnalysisAndUpload = () => emit('skipAndUpload');
const closeDialog = () => emit('close');


// 处理文件上传
const handleFileUpload = (event: UploadFile) => {
  // 检查文件类型
  const file = event.raw;
  if (!file) {
    ElMessage.error('请选择一个文件进行上传');
    return false;
  }

  const allowedTypes = ['csv', 'xlsx', 'xls'];
  const fileExtension = file.name.split('.').pop()?.toLowerCase();

  if (!fileExtension || !allowedTypes.includes(fileExtension)) {
    ElMessage.error('只支持 CSV 和 Excel 文件格式');
    return false;
  }

  // 如果文件名为空，则使用文件名
  if (!fileName.value) {
    fileName.value = file.name.split('.')[0];
  }

  selectedFile.value = file;
  return false; // 阻止 el-upload 默认上传行为
};

// 处理文件拖放
const handleDragover = () => {
  dragover.value = true;
};

const handleDragleave = () => {
  dragover.value = false;
};
</script>

<template>
  <div class="upload-info">
    <!-- 文件详情 -->
    <div v-if="selectedFile" class="file-details">
      <div class="file-icon">
        <el-icon size="48" color="#409EFF">
          <Document />
        </el-icon>
      </div>
      <div class="file-meta">
        <div class="file-name">{{ fileName }}</div>
        <div class="file-size">{{ selectedFile ? (selectedFile.size / 1024 / 1024).toFixed(2) : 0 }} MB</div>
        <div class="file-type">{{ selectedFile?.name.split('.').pop()?.toUpperCase() }} 文件</div>
      </div>
    </div>
    <div v-else>
      <div class="upload-section">
        <el-upload ref="uploadRef" class="upload-area" drag action="#" :auto-upload="false" :show-file-list="false"
          :on-change="handleFileUpload" :multiple="false" @dragover="handleDragover"
          @dragleave="handleDragleave">
          <div class="upload-content" :class="{ 'active-drag': dragover }">
            <el-icon class="upload-icon" size="60" color="#409EFF">
              <UploadFilled />
            </el-icon>
            <div class="upload-text">
              <h4>拖拽文件到此处，或 <em>点击上传</em></h4>
              <p>支持 CSV、Excel (.xlsx, .xls) 文件</p>
            </div>
          </div>
        </el-upload>
      </div>
    </div>

    <!-- 文件元数据编辑 -->
    <div class="file-metadata">
      <el-form label-width="80px" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="文件名称">
              <el-input v-model="fileName" placeholder="请输入文件名称" :prefix-icon="Document" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文件描述">
              <el-input v-model="fileDescription" placeholder="请输入文件描述信息" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </div>

    <!-- 智能分析选项 -->
    <div class="smart-analysis-options">
      <div class="options-header">
        <h4>智能分析选项</h4>
        <el-button type="text" @click="showAdvancedOptions = !showAdvancedOptions">
          {{ showAdvancedOptions ? '收起高级选项' : '展开高级选项' }}
          <el-icon>
            <ArrowRight v-if="!showAdvancedOptions" />
            <ArrowDown v-else />
          </el-icon>
        </el-button>
      </div>

      <div class="basic-options">
        <el-form-item label="自定义清洗要求">
          <el-input v-model="userRequirements" type="textarea"
            placeholder="例如：请重点关注数据标准化，确保所有列名都符合命名规范，处理缺失值，并验证邮箱格式..." :rows="3" show-word-limit maxlength="500" />
          <div class="hint-text">
            <Icon icon="material-symbols:info-outline-rounded" width="16" height="16" color="#6b7280" />
            描述您的具体清洗需求，AI将根据您的要求生成个性化的清洗建议
          </div>
        </el-form-item>
      </div>

      <el-collapse-transition>
        <div v-show="showAdvancedOptions" class="advanced-options">
          <el-form-item label="选择AI模型">
            <el-select v-model="selectedModel" placeholder="请选择AI模型">
              <el-option v-for="model in availableModels" :key="model.value" :label="model.label"
                :value="model.value" />
            </el-select>
            <div class="hint-text">
              <Icon icon="material-symbols:info-outline-rounded" width="16" height="16" color="#6b7280" />
              不同模型在字段理解和建议生成方面各有特色
            </div>
          </el-form-item>
        </div>
      </el-collapse-transition>
    </div>

    <!-- 操作按钮 -->
    <div class="file-actions">
      <el-button @click="closeDialog" size="large">
        取消
      </el-button>
      <el-button type="primary" @click="skipAnalysisAndUpload" size="large">
        <el-icon style="margin-right: 4px;">
          <Upload />
        </el-icon>
        跳过分析，直接上传
      </el-button>
      <el-button type="success" @click="startAnalysis" :loading="isAnalyzing" size="large">
        <el-icon style="margin-right: 4px;">
          <DataAnalysis />
        </el-icon>
        开始智能分析
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.upload-info {
  .upload-section {
    margin-bottom: 30px;
  }

  .upload-area {
    width: 100%;

    :deep(.el-upload) {
      width: 100%;
    }

    :deep(.el-upload-dragger) {
      width: 100%;
      height: 200px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .upload-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 20px;

      &.active-drag {
        background-color: #f0f7ff;
      }

      .upload-icon {
        margin-bottom: 16px;
        display: flex;
        justify-content: center;
        align-items: center;
      }

      .upload-text {
        text-align: center;

        h4 {
          font-size: 16px;
          font-weight: 500;
          margin-bottom: 8px;

          em {
            color: #1d4ed8;
            font-style: normal;
            font-weight: 600;
          }
        }

        p {
          font-size: 14px;
          color: #6b7280;
        }
      }

      .selected-file {
        margin-top: 16px;
        padding: 8px 16px;
        background-color: #f0f7ff;
        border-radius: 8px;

        p {
          font-size: 14px;
          color: #1d4ed8;
          font-weight: 500;
        }
      }
    }
  }

  .file-details {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    padding: 16px;
    background: white;
    border-radius: 8px;
    border: 1px solid #e5e7eb;

    .file-icon {
      flex-shrink: 0;
    }

    .file-meta {
      flex: 1;

      .file-name {
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 4px;
      }

      .file-size {
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 2px;
      }

      .file-type {
        font-size: 12px;
        color: #9ca3af;
      }
    }
  }

  .smart-analysis-options {
    margin-bottom: 24px;
    padding: 20px;
    background: white;
    border-radius: 8px;
    border: 1px solid #e5e7eb;

    .options-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;

      h4 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f2937;
      }
    }

    .basic-options {
      margin-bottom: 16px;

      .hint-text {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
      }
    }

    .advanced-options {
      .hint-text {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
      }
    }
  }

  .file-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 24px;

    .el-button {
      padding: 12px 24px;
      border-radius: 8px;
      font-weight: 500;
    }
  }
}

.file-metadata {
  margin: 16px 0;
  padding: 16px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e5e7eb;

  .el-form-item {
    margin-bottom: 16px;

    :deep(.el-form-item__label) {
      font-weight: 500;
      color: #374151;
    }

    :deep(.el-input__wrapper) {
      border-radius: 6px;
      transition: all 0.3s ease;

      &.is-focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
      }
    }

    :deep(.el-textarea__inner) {
      border-radius: 6px;
      transition: all 0.3s ease;

      &:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .upload-info {
    .file-details {
      margin-bottom: 12px;

      .file-name {
        font-size: 16px;
      }

      .file-size {
        font-size: 12px;
      }
    }

    .file-actions {
      flex-direction: column;
      gap: 8px;

      .el-button {
        width: 100%;
        padding: 10px;
        font-size: 14px;
      }
    }
  }
}
</style>
