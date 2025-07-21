<script setup lang="ts">
import { useModelStore } from '@/stores/model';
import { useSessionStore } from '@/stores/session';
import type { Model, LLMModel } from '@/types';
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, ref } from 'vue';

const sessionStore = useSessionStore();
const modelStore = useModelStore();

// 响应式数据
const loading = ref<boolean>(false);
const models = ref<Model[]>([]);
const showModelDialog = ref<boolean>(false);
const selectedModel = ref<Model | null>(null);

// 新增：标签页和LLM模型相关状态
const activeTab = ref<string>('llm');
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
    models: ['deepseek-chat', 'deepseek-coder'],
    defaultUrl: 'https://api.deepseek.com/v1'
  }
];

// 方法
const refreshModels = async (): Promise<void> => {
  loading.value = true;
  try {
    const sessionId = sessionStore.currentSession?.id;
    if (sessionId) {
      const response = await modelStore.getModels(sessionId);
      models.value = response.models || [];
    }
  } catch (error) {
    console.error('刷新模型失败:', error);
    ElMessage.error('获取模型列表失败');
  } finally {
    loading.value = false;
  }
};

const formatDate = (timestamp: string | undefined): string => {
  if (!timestamp) return '未知';
  const date = new Date(timestamp);
  return date.toLocaleString();
};

const viewModel = (model: Model): void => {
  selectedModel.value = model;
  showModelDialog.value = true;
};

const deleteModel = async (modelId: string): Promise<void> => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个模型吗？此操作不可撤销。',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    await modelStore.deleteModel(modelId);
    await refreshModels();
    ElMessage.success('模型删除成功');
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除模型失败:', error);
      ElMessage.error('删除模型失败');
    }
  }
};

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

const editLLMModel = (model: any): void => {
  currentEditLLMModel.value = model;
  llmModelForm.value = {
    name: model.name,
    provider: model.provider,
    apiKey: model.apiKey || '',
    apiUrl: model.apiUrl || '',
    modelName: model.name
  };
  showEditLLMDialog.value = true;
};

const deleteLLMModel = async (modelId: string): Promise<void> => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个LLM模型配置吗？',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    // 调用store的删除方法
    await modelStore.deleteCustomModel(modelId);
    ElMessage.success('LLM模型配置删除成功');
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除LLM模型失败:', error);
      ElMessage.error('删除LLM模型失败');
    }
  }
};

const saveLLMModel = async (): Promise<void> => {
  try {
    if (!llmModelForm.value.name || !llmModelForm.value.provider || !llmModelForm.value.apiKey) {
      ElMessage.error('请填写完整的模型信息');
      return;
    }

    await modelStore.submitCustomModel({
      name: llmModelForm.value.name,
      provider: llmModelForm.value.provider,
      api_key: llmModelForm.value.apiKey,
      api_url: llmModelForm.value.apiUrl,
      model_name: llmModelForm.value.modelName
    });

    ElMessage.success('LLM模型配置保存成功');
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

// 生命周期
onMounted(async () => {
  await refreshModels();
  await fetchLLMModels();
});
</script>

<template>
  <div class="models-page">
    <div class="page-header">
      <div class="header-content">
        <h1>模型管理</h1>
        <p class="header-subtitle">管理您的机器学习模型和LLM模型配置</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshModels" :loading="loading">
          <el-icon>
            <Refresh />
          </el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="models-tabs">
      <el-tabs v-model="activeTab" class="model-tabs">
        <el-tab-pane label="LLM模型配置" name="llm">
          <div class="llm-models-section">
            <div class="section-header">
              <h2>大语言模型配置</h2>
              <el-button type="primary" @click="showAddLLMDialog = true">
                <el-icon><Plus /></el-icon>
                添加模型
              </el-button>
            </div>
            
            <!-- LLM模型列表 -->
            <div class="llm-models-grid">
              <el-card v-for="llmModel in llmModels" :key="llmModel.id" class="llm-model-card" shadow="hover">
                <div class="llm-model-header">
                  <div class="model-icon">
                    <el-icon><Setting /></el-icon>
                  </div>
                  <div class="model-info">
                    <h3>{{ llmModel.name }}</h3>
                    <p class="model-provider">{{ llmModel.provider }}</p>
                  </div>
                  <div class="model-status">
                    <el-tag :type="llmModel.available ? 'success' : 'danger'" size="small">
                      {{ llmModel.available ? '已配置' : '未配置' }}
                    </el-tag>
                  </div>
                </div>
                <div class="llm-model-actions">
                  <el-button size="small" @click="editLLMModel(llmModel)">
                    <el-icon><Edit /></el-icon>
                    配置
                  </el-button>
                  <el-button size="small" type="danger" @click="deleteLLMModel(llmModel.id)" v-if="llmModel.id.startsWith('custom-')">
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-button>
                </div>
              </el-card>
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="训练模型" name="ml">
          <div class="models-content">
            <!-- 空状态 -->
            <div v-if="!loading && models.length === 0" class="empty-state">
              <el-empty description="暂无训练模型" :image-size="120">
                <template #description>
                  <p>还没有训练任何机器学习模型</p>
                  <p class="empty-tip">在对话分析中使用模型训练功能来创建模型</p>
                </template>
                <el-button type="primary" @click="$router.push('/chat-analysis')">
                  开始对话分析
                </el-button>
              </el-empty>
            </div>

            <!-- 模型列表 -->
            <div v-else-if="!loading" class="models-list">
              <el-card v-for="model in models" :key="model.id" class="model-card" shadow="hover">
                <div class="model-header">
                  <div class="model-info">
                    <h3>{{ model.name || model.type }}</h3>
                    <div class="model-meta">
                      <span class="meta-item">
                        <el-icon>
                          <Calendar />
                        </el-icon>
                        {{ formatDate(model.created_at) }}
                      </span>
                      <span class="meta-item">
                        <el-icon>
                          <DataAnalysis />
                        </el-icon>
                        目标变量: {{ model.target_column }}
                      </span>
                      <span class="meta-item">
                        <el-icon>
                          <TrendCharts />
                        </el-icon>
                        评分: {{ model.score.toFixed(3) }}
                      </span>
                      <span class="meta-item">
                        <el-icon>
                          <Star />
                        </el-icon>
                        准确率: {{ (model.accuracy * 100).toFixed(1) }}%
                      </span>
                    </div>
                  </div>
                  <div class="model-actions">
                    <el-tag :type="model.status === 'trained' ? 'success' : 'warning'" size="small">
                      {{ model.status }}
                    </el-tag>
                    <el-button size="small" @click="viewModel(model)">
                      <el-icon>
                        <View />
                      </el-icon>
                      查看
                    </el-button>
                    <el-button size="small" type="danger" @click="deleteModel(model.id)">
                      <el-icon>
                        <Delete />
                      </el-icon>
                      删除
                    </el-button>
                  </div>
                </div>

                <div class="model-features">
                  <h4>特征变量 ({{ model.feature_count }}个)</h4>
                  <div class="features-list">
                    <el-tag v-for="feature in model.features.slice(0, 6)" :key="feature" size="small" class="feature-tag">
                      {{ feature }}
                    </el-tag>
                    <el-tag v-if="model.features.length > 6" size="small" type="info">
                      +{{ model.features.length - 6 }}个
                    </el-tag>
                  </div>
                </div>
              </el-card>
            </div>

            <!-- 加载状态 -->
            <div v-if="loading" class="loading-state">
              <el-skeleton :rows="3" animated />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 模型详情对话框 -->
    <el-dialog v-model="showModelDialog" title="模型详情" width="70%" class="model-dialog">
      <div v-if="selectedModel" class="model-detail">
        <div class="detail-row">
          <label>模型名称:</label>
          <span>{{ selectedModel.name || selectedModel.type }}</span>
        </div>
        <div class="detail-row">
          <label>模型类型:</label>
          <span>{{ selectedModel.type }}</span>
        </div>
        <div class="detail-row">
          <label>目标变量:</label>
          <span>{{ selectedModel.target_column }}</span>
        </div>
        <div class="detail-row">
          <label>模型评分:</label>
          <span>{{ selectedModel.score.toFixed(3) }}</span>
        </div>
        <div class="detail-row">
          <label>准确率:</label>
          <span>{{ (selectedModel.accuracy * 100).toFixed(1) }}%</span>
        </div>
        <div class="detail-row">
          <label>状态:</label>
          <el-tag :type="selectedModel.status === 'trained' ? 'success' : 'warning'">
            {{ selectedModel.status }}
          </el-tag>
        </div>
        <div class="detail-row">
          <label>版本:</label>
          <span>{{ selectedModel.version }}</span>
        </div>
        <div class="detail-row">
          <label>创建时间:</label>
          <span>{{ formatDate(selectedModel.created_at) }}</span>
        </div>
        <div class="detail-row" v-if="selectedModel.last_used">
          <label>最后使用:</label>
          <span>{{ formatDate(selectedModel.last_used) }}</span>
        </div>
        <div class="detail-row" v-if="selectedModel.description">
          <label>描述:</label>
          <span>{{ selectedModel.description }}</span>
        </div>
        <div class="detail-row">
          <label>特征变量 ({{ selectedModel.feature_count }}个):</label>
          <div class="features-grid">
            <el-tag v-for="feature in selectedModel.features" :key="feature" class="feature-tag">
              {{ feature }}
            </el-tag>
          </div>
        </div>
        <div class="detail-row" v-if="Object.keys(selectedModel.metrics).length > 0">
          <label>性能指标:</label>
          <div class="metrics-grid">
            <div v-for="(value, key) in selectedModel.metrics" :key="key" class="metric-item">
              <span class="metric-label">{{ key }}:</span>
              <span class="metric-value">{{ typeof value === 'number' ? value.toFixed(4) : value }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 添加LLM模型对话框 -->
    <el-dialog v-model="showAddLLMDialog" title="添加LLM模型" width="600px" @close="resetLLMForm">
      <el-form :model="llmModelForm" label-width="120px">
        <el-form-item label="提供商" required>
          <el-select v-model="llmModelForm.provider" placeholder="选择模型提供商" style="width: 100%">
            <el-option v-for="provider in modelProviders" :key="provider.name" :label="provider.name" :value="provider.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称" required>
          <el-select v-model="llmModelForm.modelName" placeholder="选择或输入模型名称" style="width: 100%" filterable allow-create>
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
            默认URL: {{ modelProviders.find(p => p.name === llmModelForm.provider)?.defaultUrl || '请选择提供商' }}
          </div>
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="llmModelForm.name" placeholder="自定义显示名称（可选）" />
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
    <el-dialog v-model="showEditLLMDialog" title="编辑LLM模型" width="600px" @close="resetLLMForm">
      <el-form :model="llmModelForm" label-width="120px">
        <el-form-item label="提供商" required>
          <el-select v-model="llmModelForm.provider" placeholder="选择模型提供商" style="width: 100%">
            <el-option v-for="provider in modelProviders" :key="provider.name" :label="provider.name" :value="provider.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称" required>
          <el-select v-model="llmModelForm.modelName" placeholder="选择或输入模型名称" style="width: 100%" filterable allow-create>
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
            默认URL: {{ modelProviders.find(p => p.name === llmModelForm.provider)?.defaultUrl || '请选择提供商' }}
          </div>
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="llmModelForm.name" placeholder="自定义显示名称（可选）" />
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
</template>

<style scoped>
.models-page {
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

.header-content h1 {
  margin: 0 0 8px 0;
  font-size: 32px;
  font-weight: 700;
  color: #1f2937;
}

.header-subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 16px;
  font-weight: 400;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.models-content {
  margin-top: 24px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 16px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(226, 232, 240, 0.6);
}

.empty-tip {
  color: #64748b;
  margin-top: 8px;
}

.models-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
}

.model-card {
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.model-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.model-info h3 {
  margin: 0 0 12px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
}

.model-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.model-actions {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 14px;
}

.model-features h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 500;
  color: #374151;
}

.features-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.feature-tag {
  margin: 0;
}

.loading-state {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 24px;
  backdrop-filter: blur(10px);
}

/* 模型详情对话框样式 */
.model-dialog .el-dialog__body {
  padding: 24px;
}

.model-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.detail-row label {
  min-width: 120px;
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.detail-row span {
  color: #64748b;
  font-size: 14px;
}

.features-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  flex: 1;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(248, 250, 252, 0.8);
  border-radius: 8px;
  border: 1px solid rgba(226, 232, 240, 0.6);
}

.metric-label {
  font-weight: 500;
  color: #374151;
  font-size: 13px;
}

.metric-value {
  font-weight: 600;
  color: #1e293b;
  font-size: 13px;
}

/* LLM模型相关样式 */
.models-tabs {
  margin-top: 24px;
}

.model-tabs {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(226, 232, 240, 0.6);
}

.llm-models-section {
  padding: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.section-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.llm-models-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
}

.llm-model-card {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
  background: white;
}

.llm-model-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.llm-model-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.model-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.model-info {
  flex: 1;
}

.model-info h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.model-provider {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

.model-status {
  flex-shrink: 0;
}

.llm-model-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}
</style>
