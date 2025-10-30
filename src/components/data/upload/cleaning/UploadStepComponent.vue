<script setup lang="ts">
import type { LLMModel } from '@/types';
import { DataAnalysis, Document, Upload, UploadFilled } from '@element-plus/icons-vue';
import { Icon } from '@iconify/vue';
import { ElButton, ElCol, ElCollapseTransition, ElForm, ElFormItem, ElIcon, ElInput, ElMessage, ElOption, ElOptionGroup, ElRow, ElSelect, ElTag, ElUpload, type UploadFile } from 'element-plus';
import { ref } from 'vue';

// 双向绑定数据
const fileName = defineModel<string>('fileName', { required: true });
const fileDescription = defineModel<string>('fileDescription', { required: true });
const userRequirements = defineModel<string>('userRequirements', { required: true });
const selectedModel = defineModel<string>('selectedModel', { required: true });
const selectedFile = defineModel<File | null>('selectedFile', { required: true });

// 定义组件属性
const props = defineProps<{
  isAnalyzing: boolean;
  availableModels: LLMModel[];
}>();

// 定义组件事件
const emit = defineEmits<{
  analyze: [];
  skipAndUpload: [];
  close: [];
}>();

// 文件上传相关状态
const dragover = ref(false);
const isHovering = ref(false);

// 按提供商分组模型
const getProviderGroups = () => {
  const groups: { name: string; models: LLMModel[]; }[] = [];
  const providers = new Set(props.availableModels.map(m => m.provider));

  providers.forEach(provider => {
    const models = props.availableModels.filter(m => m.provider === provider);
    groups.push({
      name: provider,
      models: models
    });
  });

  return groups;
};

// 处理函数
const startAnalysis = () => emit('analyze');
const skipAnalysisAndUpload = () => emit('skipAndUpload');
const closeDialog = () => emit('close');

// 清除已选择的文件
const clearSelectedFile = () => {
  selectedFile.value = null;
  fileName.value = '';
  fileDescription.value = '';
};

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
      <div class="file-actions">
        <el-button class="delete-btn" text circle @click="clearSelectedFile" :title="'删除当前文件'">
          <Icon icon="material-symbols:close-rounded" width="20" height="20" />
        </el-button>
      </div>
    </div>
    <div v-else>
      <div class="upload-section">
        <el-upload ref="uploadRef" class="upload-area" :class="{ 'hovering': isHovering }" drag action="#" :auto-upload="false" :show-file-list="false"
          :on-change="handleFileUpload" :multiple="false" @dragover="handleDragover"
          @dragleave="handleDragleave" @mouseenter="isHovering = true" @mouseleave="isHovering = false">
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

      <!-- 直接展示模型选择，无需展开 -->
      <div class="advanced-options">
        <el-form-item label="选择AI模型">
          <el-select v-model="selectedModel" placeholder="请选择AI模型">
            <!-- 按提供商分组显示模型 -->
            <el-option-group v-for="provider in getProviderGroups()" :key="provider.name" :label="provider.name">
              <el-option v-for="model in provider.models" :key="model.id"
                :label="model.name" :value="model.id">
                <div class="model-option">
                  <span class="model-name">{{ model.name }}</span>
                  <el-tag :type="model.available ? 'success' : 'danger'" size="small" class="model-tag">
                    {{ model.available ? '已配置' : '未配置' }}
                  </el-tag>
                </div>
              </el-option>
            </el-option-group>
          </el-select>
          <div class="hint-text">
            <Icon icon="material-symbols:info-outline-rounded" width="16" height="16" color="#6b7280" />
            不同模型在字段理解和建议生成方面各有特色
          </div>
        </el-form-item>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="file-actions">
      <el-button @click="closeDialog" size="large">
        取消
      </el-button>
      <el-button type="primary" :disabled="!selectedFile" :loading="isAnalyzing" size="large" @click="startAnalysis">
        <el-icon style="margin-right: 4px;">
          <DataAnalysis />
        </el-icon>
        开始智能分析
      </el-button>
      <el-button type="success" plain size="large" @click="skipAnalysisAndUpload">
        <el-icon style="margin-right: 4px;">
          <Upload />
        </el-icon>
        跳过分析，直接上传
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.upload-info {
  .upload-section {
    margin-bottom: 24px;

    .upload-area {
      width: 100%;
      border: none; /* 去掉外部虚线边框 */
      border-radius: 8px;
      padding: 0; /* 扩展到外层尺寸 */

      :deep(.el-upload-dragger) {
        width: 100%;
        min-height: 220px; /* 高度扩大 */
        border: 2px dashed #d1d5db;
        border-radius: 8px;
        padding: 24px 28px;
        box-sizing: border-box;
        transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
        display: flex;               /* 居中容器 */
        align-items: center;         /* 垂直居中 */
        justify-content: center;     /* 水平居中 */
        text-align: center;          /* 文本居中 */
      }

      &.hovering :deep(.el-upload-dragger) {
        border-color: #3b82f6;
        background-color: #f0f7ff;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12) inset;
      }

      &.hovering .upload-icon {
        animation: pulse 1.2s ease-in-out infinite;
      }

      .upload-content {
        display: flex;
        align-items: center;
        justify-content: center;     /* 将图标和文字整体居中 */
        gap: 16px;
      }

      .upload-icon {
        margin-right: 16px;
        transition: transform 0.2s ease;
      }

      .upload-text {
        h4 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
        }

        em {
          color: #1d4ed8;
          font-style: normal;
        }

        p {
          font-size: 14px;
          color: #6b7280;
        }
      }

      @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.06); }
        100% { transform: scale(1); }
      }
    }
  }

  .file-details {
    position: relative; /* 让删除按钮可以定位到右上角 */
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

    .file-actions {
      position: absolute;
      top: 8px;
      right: 8px;
    }

    .delete-btn {
      color: #ef4444;
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
    }

    .advanced-options {
      margin-top: 8px;
    }

    .hint-text {
      margin-top: 6px;
      font-size: 12px;
      color: #6b7280;
    }

    .model-option {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;

      .model-name {
        margin-right: 8px;
      }
    }
  }

  .file-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
    gap: 12px;
  }
}
</style>
