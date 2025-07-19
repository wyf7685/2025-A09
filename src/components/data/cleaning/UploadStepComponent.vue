<script setup lang="ts">
import { ArrowDown, ArrowRight, DataAnalysis, Document, InfoFilled, Upload } from '@element-plus/icons-vue';
import { ref } from 'vue';

// 双向绑定数据
const userRequirements = defineModel<string>('userRequirements', { default: '' });
const selectedModel = defineModel<string>('selectedModel', { default: '' });
const fileMetadata = defineModel<{ name: string, description: string; }>('fileMetadata', { required: true });

// 定义组件属性
defineProps<{
  file: File | null;
  isAnalyzing: boolean;
  availableModels: Array<{ value: string, label: string; }>;
}>();

// 定义组件事件
const emit = defineEmits<{
  analyze: [];
  skipAndUpload: [];
  close: [];
}>();

// 高级选项显示状态
const showAdvancedOptions = ref(false);

// 处理函数
const startAnalysis = () => emit('analyze');
const skipAnalysisAndUpload = () => emit('skipAndUpload');
const closeDialog = () => emit('close');
</script>

<template>
  <div class="upload-info">
    <!-- 文件详情 -->
    <div class="file-details">
      <div class="file-icon">
        <el-icon size="48" color="#667eea">
          <Document />
        </el-icon>
      </div>
      <div class="file-meta">
        <div class="file-name">{{ fileMetadata.name }}</div>
        <div class="file-size">{{ file ? (file.size / 1024 / 1024).toFixed(2) : 0 }} MB</div>
        <div class="file-type">{{ file?.name.split('.').pop()?.toUpperCase() }} 文件</div>
      </div>
    </div>

    <!-- 文件元数据编辑 -->
    <div class="file-metadata">
      <el-form label-width="80px" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="文件名称">
              <el-input v-model="fileMetadata.name" placeholder="请输入文件名称" :prefix-icon="Document" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文件描述">
              <el-input v-model="fileMetadata.description" placeholder="请输入文件描述信息" />
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
            <el-icon>
              <InfoFilled />
            </el-icon>
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
              <el-icon>
                <InfoFilled />
              </el-icon>
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
        <el-icon>
          <Upload />
        </el-icon>
        跳过分析，直接上传
      </el-button>
      <el-button type="success" @click="startAnalysis" :loading="isAnalyzing" size="large">
        <el-icon>
          <DataAnalysis />
        </el-icon>
        开始智能分析
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.upload-info {
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
