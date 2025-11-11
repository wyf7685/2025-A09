<script setup lang="ts">
import LLMModelIcon from '@/components/LLMModelIcon.vue';
import PageHeader from '@/components/PageHeader.vue';
import { useModelStore } from '@/stores/model';
import type { LLMModel, LLMModelEditParams } from '@/types';
import { Delete, Edit, Plus } from '@element-plus/icons-vue';
import { Icon } from '@iconify/vue';
import {
  ElButton, ElCard, ElDialog, ElForm, ElFormItem, ElIcon,
  ElInput, ElMessage, ElMessageBox, ElOption, ElSelect
} from 'element-plus';
import { onMounted, ref, watch } from 'vue';

const modelStore = useModelStore();

// 响应式数据
const llmModels = ref<LLMModel[]>([]);
const showAddLLMDialog = ref<boolean>(false);
const showEditLLMDialog = ref<boolean>(false);
const currentEditLLMModel = ref<LLMModel | null>(null);

// LLM模型表单数据
const llmModelForm = ref({
  name: '',
  provider: '',
  apiKey: '',
  apiUrl: '',
  modelName: ''
});

// 获取模型状态颜色
const getStatusColor = (available: boolean): string => {
  return available ? '#10b981' : '#ef4444';
};

// 获取提供商颜色
const getProviderColor = (provider: string): string => {
  const colorMap: Record<string, string> = {
    'OpenAI': '#00a67e',
    'Google': '#4285f4',
    'DeepSeek': '#8b5cf6',
    'Ollama': '#000000',
    'ZhipuAI': '#1e88e5',
    // 'Anthropic': '#d97706',
  };
  return colorMap[provider] || '#6b7280';
};

// 预设的模型提供商
const modelProviders = [
  {
    name: 'OpenAI',
    models: ['gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo'],
    defaultUrl: 'https://api.openai.com/v1'
  },
  {
    name: 'Google',
    models: ['gemini-2.0-flash', 'gemini-1.5-pro'],
    defaultUrl: 'https://generativelanguage.googleapis.com/v1beta'
  },
  {
    name: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    defaultUrl: 'https://api.deepseek.com/v1'
  },
  {
    name: 'Ollama',
    models: ['llama3.2', 'llama3.1', 'qwen2.5', 'mistral', 'gemma2'],
    defaultUrl: 'http://localhost:11434'
  },
  {
    name: 'ZhipuAI',
    models: ['glm-4.5', 'glm-4.5-air', 'glm-4.6'],
    defaultUrl: 'https://open.bigmodel.cn/api/paas/v4'
  },
];

// LLM模型管理方法
const fetchLLMModels = async (): Promise<void> => {
  try {
    await modelStore.fetchAvailableModels();
    llmModels.value = modelStore.availableModels;
  } catch (error) {
    console.error('获取LLM模型失败:', error);
    ElMessage.error('获取LLM模型列表失败');
  }
};

const editLLMModel = async (model: LLMModel): Promise<void> => {
  currentEditLLMModel.value = model;

  try {
    const customModelConfig = await modelStore.getCustomModel(model.id);
    llmModelForm.value = {
      name: customModelConfig.name,
      provider: customModelConfig.provider,
      apiKey: '', // 编辑时不显示已存储的API Key，用户需要重新输入或保持不变
      apiUrl: customModelConfig.api_url || '',
      modelName: customModelConfig.model_name
    };
  } catch (error) {
    console.error('获取模型配置失败:', error);
    ElMessage.error('获取模型配置失败');
    return;
  }

  showEditLLMDialog.value = true;
};

const addNewLLMModel = (): void => {
  currentEditLLMModel.value = null;
  llmModelForm.value = {
    name: '',
    provider: '',
    apiKey: '',
    apiUrl: '',
    modelName: ''
  };
  showAddLLMDialog.value = true;
};

const getDefaultApiUrl = (provider: string): string => {
  const defaultUrls: Record<string, string> = {
    'Google': 'https://generativelanguage.googleapis.com/v1beta',
    'OpenAI': 'https://api.openai.com/v1',
    'DeepSeek': 'https://api.deepseek.com/v1',
    'Ollama': 'http://localhost:11434',
    'ZhipuAI': 'https://open.bigmodel.cn/api/paas/v4',
    'Anthropic': 'https://api.anthropic.com/v1'
  };
  return defaultUrls[provider] || '';
};

const getDialogTitle = (): string => {
  if (currentEditLLMModel.value) {
    return `编辑 ${currentEditLLMModel.value.name}`;
  } else {
    return '添加新模型';
  }
};

const deleteLLMModel = async (modelId: string): Promise<void> => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个模型配置吗？',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    // 调用store的删除方法
    await modelStore.deleteCustomModel(modelId);
    ElMessage.success('模型配置删除成功');
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除模型失败:', error);
      ElMessage.error('删除模型失败');
    }
  }
};

const saveLLMModel = async (): Promise<void> => {
  try {
    // 新增模型时，name、provider、apiKey、modelName 都是必填的
    // 编辑模型时，apiKey 是可选的（不填则保持原值）
    if (!llmModelForm.value.name || !llmModelForm.value.provider || !llmModelForm.value.modelName) {
      ElMessage.error('请填写完整的模型信息');
      return;
    }

    // 新增时必须填写 API Key
    if (!currentEditLLMModel.value && !llmModelForm.value.apiKey) {
      ElMessage.error('请填写 API Key');
      return;
    }

    // 如果用户没有填写 API URL，使用默认值
    const finalApiUrl = llmModelForm.value.apiUrl.trim() || getDefaultApiUrl(llmModelForm.value.provider);

    // 直接使用选择的模型名称作为API调用名称（因为它来自预设列表，保证正确）
    const apiModelName = llmModelForm.value.modelName;

    if (currentEditLLMModel.value) {
      // 编辑现有模型
      const updateData: LLMModelEditParams = {
        name: llmModelForm.value.name,
        provider: llmModelForm.value.provider,
        api_url: finalApiUrl,
        model_name: llmModelForm.value.modelName,
        api_model_name: apiModelName
      };
      // 只有当用户填写了新的 API Key 时才更新它
      if (llmModelForm.value.apiKey.trim()) {
        updateData.api_key = llmModelForm.value.apiKey;
      }
      await modelStore.updateCustomModel(currentEditLLMModel.value.id, updateData);
      ElMessage.success('模型配置更新成功');
    } else {
      // 添加新模型
      await modelStore.submitCustomModel({
        name: llmModelForm.value.name,
        provider: llmModelForm.value.provider,
        api_key: llmModelForm.value.apiKey,
        api_url: finalApiUrl,
        model_name: llmModelForm.value.modelName,
        api_model_name: apiModelName
      });
      ElMessage.success('新模型配置添加成功');
    }

    showAddLLMDialog.value = false;
    showEditLLMDialog.value = false;
    await fetchLLMModels();
  } catch (error) {
    console.error('保存LLM模型失败:', error);
    ElMessage.error('保存LLM模型配置失败');
  }
};

const resetLLMForm = (): void => {
  llmModelForm.value = {
    name: '',
    provider: '',
    apiKey: '',
    apiUrl: '',
    modelName: ''
  };
  currentEditLLMModel.value = null;
};

// 监听提供商变化，自动填充默认 URL（仅当 URL 为空时）
watch(() => llmModelForm.value.provider, (newProvider) => {
  if (newProvider && !llmModelForm.value.apiUrl.trim()) {
    const provider = modelProviders.find(p => p.name === newProvider);
    if (provider) {
      llmModelForm.value.apiUrl = provider.defaultUrl;
    }
  }
});

// 生命周期
onMounted(async () => {
  await fetchLLMModels();
});
</script>

<template>
  <div class="llm-models-page">
    <div class="page-header">
      <!-- <div class="header-content">
        <h1>大语言模型管理</h1>
        <p class="header-subtitle">配置和管理您的大语言模型API</p>
      </div> -->
      <PageHeader
        title="大语言模型管理"
        subtitle="配置和管理您的大语言模型API" />
      <div class="header-actions">
        <el-button type="primary" @click="showAddLLMDialog = true">
          <el-icon>
            <Plus />
          </el-icon>
          添加模型
        </el-button>
      </div>
    </div>

    <div class="llm-models-container">
      <!-- LLM模型列表 -->
      <div v-if="llmModels.length > 0" class="llm-models-grid">
        <el-card v-for="llmModel in llmModels" :key="llmModel.id" class="llm-model-card" shadow="hover">
          <div class="llm-model-header">
            <div class="model-icon"
              :style="{ background: `linear-gradient(135deg, ${getProviderColor(llmModel.provider)}15, ${getProviderColor(llmModel.provider)}25)` }">
              <LLMModelIcon :provider="llmModel.provider" :size="28" />
            </div>
            <div class="model-info">
              <h3>{{ llmModel.name }}</h3>
              <div class="model-details">
                <span class="model-provider">{{ llmModel.provider }}</span>
              </div>
            </div>
            <div class="model-status">
              <div class="status-indicator" :class="{ 'status-active': llmModel.available }">
                <Icon
                  :icon="llmModel.available ? 'material-symbols:check-circle' : 'material-symbols:error-circle-rounded'"
                  width="16"
                  height="16"
                  :color="getStatusColor(llmModel.available ?? false)" />
                <span class="status-text">{{ llmModel.available ? '已配置' : '未配置' }}</span>
              </div>
            </div>
          </div>
          <div class="llm-model-actions">
            <el-button size="small" type="primary" plain @click="editLLMModel(llmModel)">
              <el-icon>
                <Edit />
              </el-icon>
              编辑配置
            </el-button>
            <el-button size="small" type="danger" plain @click="deleteLLMModel(llmModel.id)">
              <el-icon>
                <Delete />
              </el-icon>
              删除
            </el-button>
          </div>
        </el-card>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <div class="empty-content">
          <div class="empty-icon">
            <Icon icon="material-symbols:psychology-alt-outline" width="80" height="80" color="#d1d5db" />
          </div>
          <h3>暂无配置的模型</h3>
          <p>开始添加您的第一个大语言模型配置</p>
          <el-button type="primary" size="large" @click="addNewLLMModel()">
            <el-icon>
              <Plus />
            </el-icon>
            添加第一个模型
          </el-button>
        </div>
      </div>

      <!-- 添加LLM模型对话框 -->
      <el-dialog v-model="showAddLLMDialog" title="添加LLM模型" width="600px" @close="resetLLMForm">
        <el-form :model="llmModelForm" label-width="120px">
          <el-form-item label="显示名称" required>
            <el-input v-model="llmModelForm.name" placeholder="自定义显示名称（可选）" />
          </el-form-item>
          <el-form-item label="提供商" required>
            <el-select v-model="llmModelForm.provider" placeholder="选择模型提供商" style="width: 100%">
              <el-option v-for="provider in modelProviders" :key="provider.name" :label="provider.name"
                :value="provider.name">
                <div class="provider-option">
                  <LLMModelIcon :provider="provider.name" :size="18" />
                  <span>{{ provider.name }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="模型名称" required>
            <el-select v-model="llmModelForm.modelName" placeholder="选择或输入模型名称" style="width: 100%" filterable
              allow-create>
              <el-option v-for="model in modelProviders.find(p => p.name === llmModelForm.provider)?.models || []"
                :key="model" :label="model" :value="model" />
            </el-select>
          </el-form-item>
          <el-form-item label="API Key" required>
            <el-input v-model="llmModelForm.apiKey" type="password" placeholder="请输入API密钥" show-password />
          </el-form-item>
          <el-form-item label="API URL">
            <el-input v-model="llmModelForm.apiUrl" placeholder="留空使用默认URL" />
            <div class="form-tip">
              默认URL: {{modelProviders.find(p => p.name === llmModelForm.provider)?.defaultUrl || '请选择提供商'}}
            </div>
          </el-form-item>
        </el-form>
        <template #footer>
          <div class="dialog-footer">
            <el-button @click="showAddLLMDialog = false">取消</el-button>
            <el-button type="primary" @click="saveLLMModel">保存</el-button>
          </div>
        </template>
      </el-dialog>

      <!-- 编辑LLM模型对话框 -->
      <el-dialog v-model="showEditLLMDialog" :title="getDialogTitle()" width="600px" @close="resetLLMForm">
        <el-form :model="llmModelForm" label-width="120px">
          <el-form-item label="显示名称" required>
            <el-input v-model="llmModelForm.name" placeholder="自定义显示名称（可选）" />
          </el-form-item>
          <el-form-item label="提供商" required>
            <el-select v-model="llmModelForm.provider" placeholder="选择模型提供商" style="width: 100%">
              <el-option v-for="provider in modelProviders" :key="provider.name" :label="provider.name"
                :value="provider.name">
                <div class="provider-option">
                  <LLMModelIcon :provider="provider.name" :size="18" />
                  <span>{{ provider.name }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="模型名称" required>
            <el-select v-model="llmModelForm.modelName" placeholder="选择或输入模型名称" style="width: 100%" filterable
              allow-create>
              <el-option v-for="model in modelProviders.find(p => p.name === llmModelForm.provider)?.models || []"
                :key="model" :label="model" :value="model" />
            </el-select>
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="llmModelForm.apiKey" type="password" placeholder="请输入API密钥" show-password />
          </el-form-item>
          <el-form-item label="API URL">
            <el-input v-model="llmModelForm.apiUrl" placeholder="留空使用默认URL" />
            <div class="form-tip">
              默认URL: {{modelProviders.find(p => p.name === llmModelForm.provider)?.defaultUrl || '请选择提供商'}}
            </div>
          </el-form-item>
        </el-form>
        <template #footer>
          <div class="dialog-footer">
            <el-button @click="showEditLLMDialog = false">取消</el-button>
            <el-button type="primary" @click="saveLLMModel">保存</el-button>
          </div>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<style scoped>
.llm-models-page {
  min-height: 100vh;
  background: #f8fafc;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding: 0 8px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.llm-models-container {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(226, 232, 240, 0.6);
}

.llm-models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
}

.llm-model-card {
  /* max-width: 480px; */
  flex-shrink: 0;
  border-radius: 16px;
  border: 1px solid #e5e7eb;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: white;
  overflow: hidden;
  position: relative;
}

.llm-model-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6, #06b6d4);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.llm-model-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  border-color: #d1d5db;
}

.llm-model-card:hover::before {
  opacity: 1;
}

.llm-model-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
  padding: 4px 0;
}

.model-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.llm-model-card:hover .model-icon {
  transform: scale(1.05);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.model-info {
  flex: 1;
  min-width: 0;
}

.model-info h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.2;
  word-break: break-word;
}

.model-details {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.model-provider {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
}

.model-status {
  flex-shrink: 0;
  align-self: flex-start;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 20px;
  background: rgba(243, 244, 246, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(229, 231, 235, 0.8);
  transition: all 0.3s ease;
}

.status-indicator.status-active {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
}

.status-text {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

.llm-model-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid rgba(229, 231, 235, 0.5);
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.02) 0%, rgba(139, 92, 246, 0.02) 100%);
  border-radius: 16px;
  border: 2px dashed rgba(209, 213, 219, 0.8);
}

.empty-content {
  text-align: center;
  max-width: 400px;
  padding: 40px 20px;
}

.empty-icon {
  margin-bottom: 24px;
  opacity: 0.8;
}

.empty-content h3 {
  margin: 0 0 12px 0;
  font-size: 20px;
  font-weight: 600;
  color: #374151;
}

.empty-content p {
  margin: 0 0 32px 0;
  color: #6b7280;
  font-size: 16px;
  line-height: 1.5;
}

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.provider-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}

.provider-option span {
  font-weight: 500;
}
</style>
