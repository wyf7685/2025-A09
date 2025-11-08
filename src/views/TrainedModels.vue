<script setup lang="ts">
import DatasetSelector from '@/components/chat/DatasetSelector.vue';
import { useModelStore } from '@/stores/model';
import type { MLModel } from '@/types';
import { Calendar, DataAnalysis, Delete, Download, Refresh, Star, View } from '@element-plus/icons-vue';
import { Icon } from '@iconify/vue';
import { ElButton, ElCard, ElDialog, ElIcon, ElMessage, ElMessageBox, ElSkeleton, ElTag } from 'element-plus';
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

const modelStore = useModelStore();
const router = useRouter();

// 响应式数据
const loading = ref<boolean>(false);
const models = ref<MLModel[]>([]);
const showModelDialog = ref<boolean>(false);
const selectedModel = ref<MLModel | null>(null);
const showAnalyzeDialog = ref<boolean>(false);
const analyzeModel = ref<MLModel | null>(null);
const sessions = ref<any[]>([]);
const loadingSessions = ref<boolean>(false);
const showDatasetSelector = ref<boolean>(false);

// 方法
const refreshModels = async (): Promise<void> => {
  loading.value = true;
  try {
    // 获取所有已注册的模型，而不是仅当前会话的模型
    const response = await modelStore.getAllModels();
    models.value = response.models || [];
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

const viewModel = (model: MLModel): void => {
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

// 打开分析对话框
const openAnalyzeDialog = async (model: MLModel): Promise<void> => {
  analyzeModel.value = model;
  showAnalyzeDialog.value = true;

  // 加载会话列表
  loadingSessions.value = true;
  try {
    await sessionStore.listSessions();
    sessions.value = sessionStore.sessions;
  } catch (error) {
    console.error('加载会话列表失败:', error);
    ElMessage.error('加载会话列表失败');
  } finally {
    loadingSessions.value = false;
  }
};

// 挂载模型到现有会话
const mountToSession = async (sessionId: string): Promise<void> => {
  if (!analyzeModel.value) return;

  try {
    await sessionStore.addModelsToSession(sessionId, [analyzeModel.value.id]);
    ElMessage.success('模型已挂载到会话');
    showAnalyzeDialog.value = false;

    // 跳转到对话页面
    router.push(`/chat-analysis?session=${sessionId}`);
  } catch (error) {
    console.error('挂载模型失败:', error);
    ElMessage.error('挂载模型失败');
  }
};

// 打开新建会话弹窗
const openNewSessionDialog = (): void => {
  showAnalyzeDialog.value = false;
  showDatasetSelector.value = true;
};

// 创建新会话并挂载模型
const createSessionAndMount = async (datasetIds: string[]): Promise<void> => {
  if (!analyzeModel.value) return;

  try {
    // 创建新会话
    const newSession = await sessionStore.createSession(datasetIds);

    // 挂载模型
    await sessionStore.addModelsToSession(newSession.id, [analyzeModel.value.id]);

    ElMessage.success('已创建新会话并挂载模型');
    showDatasetSelector.value = false;

    // 跳转到对话页面
    router.push(`/chat-analysis?session=${newSession.id}`);
  } catch (error) {
    console.error('创建会话失败:', error);
    ElMessage.error('创建会话失败');
  }
};

// 生命周期
onMounted(async () => {
  await refreshModels();
});
</script>

<template>
  <div class="trained-models-page">
    <div class="page-header">
      <div class="header-content">
        <h1>训练模型管理</h1>
        <p class="header-subtitle">管理您在对话分析过程中训练的机器学习模型</p>
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

    <div class="models-container">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <el-skeleton :rows="3" animated />
      </div>

      <!-- 空状态 -->
      <div v-else-if="models.length === 0" class="empty-state">
        <div class="empty-content">
          <div class="empty-icon">
            <Icon icon="material-symbols:model-training" />
          </div>
          <h3 class="empty-title">暂无训练模型</h3>
          <p class="empty-description">还没有训练任何机器学习模型</p>
          <p class="empty-tip">在对话分析中使用模型训练功能来创建模型</p>
          <div class="empty-action-wrapper">
            <el-button type="primary" @click="$router.push('/chat-analysis')" class="empty-action">
              <Icon icon="material-symbols:rocket-launch" class="button-icon" />
              开始对话分析
            </el-button>
          </div>
        </div>
      </div>

      <!-- 模型列表 -->
      <div v-else class="models-list">
        <el-card v-for="model in models" :key="model.id" class="model-card" shadow="hover">
          <div class="model-header">
            <div class="model-info">
              <div class="model-title">
                <h3>{{ model.name || model.type }}</h3>
                <el-tag :type="model.status === 'trained' ? 'success' : 'warning'" size="small">
                  {{ model.status }}
                </el-tag>
              </div>
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
                    <Star />
                  </el-icon>
                  准确率: {{ (model.accuracy * 100).toFixed(1) }}%
                </span>
              </div>
            </div>
            <div class="model-actions">
              <el-button size="small" type="primary" plain @click="openAnalyzeDialog(model)" class="action-btn">
                <el-icon>
                  <View />
                </el-icon>
                分析
              </el-button>
              <el-button size="small" type="success" plain @click="viewModel(model)" class="action-btn">
                <el-icon>
                  <Refresh />
                </el-icon>
                查看
              </el-button>
              <el-button size="small" type="warning" plain @click="modelStore.downloadModel(model.id)"
                class="action-btn">
                <el-icon>
                  <Download />
                </el-icon>
                下载
              </el-button>
              <el-button size="small" type="danger" plain @click="deleteModel(model.id)" class="action-btn">
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
          <div class="detail-row" v-if="selectedModel.session_name">
            <label>所属对话:</label>
            <span>{{ selectedModel.session_name }}</span>
          </div>
          <div class="detail-row" v-if="selectedModel.dataset_name">
            <label>数据集名称:</label>
            <span>{{ selectedModel.dataset_name }}</span>
          </div>
          <div class="detail-row" v-if="selectedModel.dataset_description">
            <label>数据集描述:</label>
            <span>{{ selectedModel.dataset_description }}</span>
          </div>
          <div class="detail-row">
            <label>目标变量:</label>
            <span>{{ selectedModel.target_column }}</span>
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

      <!-- 分析对话框：选择会话 -->
      <el-dialog v-model="showAnalyzeDialog" title="选择会话进行分析" width="500px">
        <div v-if="loadingSessions" class="dialog-loading">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else>
          <div class="session-list">
            <div v-if="sessions.length === 0" class="empty-sessions">
              <p>暂无可用会话</p>
            </div>
            <div v-else>
              <div v-for="session in sessions" :key="session.id" class="session-item">
                <div class="session-info">
                  <div class="session-name">{{ session.name || '未命名会话' }}</div>
                  <div class="session-meta">创建于 {{ formatDate(session.created_at) }}</div>
                </div>
                <el-button type="primary" size="small" @click="mountToSession(session.id)">
                  选择
                </el-button>
              </div>
            </div>
          </div>
          <div class="dialog-footer">
            <el-button type="success" @click="openNewSessionDialog">
              <el-icon>
                <TrendCharts />
              </el-icon>
              新建会话
            </el-button>
          </div>
        </div>
      </el-dialog>

      <!-- 数据集选择器弹窗 -->
      <DatasetSelector v-model:visible="showDatasetSelector" @create-session="createSessionAndMount"
        @go-to-data="$router.push('/data-management')" />
    </div>
  </div>
</template>

<style scoped>
.trained-models-page {
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

/* 修复图标对齐问题 */
:deep(.el-icon) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
}

/* 为按钮中的图标添加适当的间距 */
.action-btn :deep(.el-icon) {
  margin-right: 4px;
}

/* 调整查看按钮位置，使其向左移动 */
.model-actions .action-btn:nth-child(2) {
  margin-left: -0px;
}

models-container {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(226, 232, 240, 0.6);
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

.empty-content {
  text-align: center;
  max-width: 400px;
}

.empty-icon {
  font-size: 80px;
  color: #ec4899;
  margin-bottom: 24px;
  filter: drop-shadow(0 4px 12px rgba(236, 72, 153, 0.2));
}

.empty-title {
  margin: 0 0 16px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1e293b;
}

.empty-description {
  margin: 0 0 8px 0;
  color: #64748b;
  font-size: 16px;
  line-height: 1.5;
}

.empty-tip {
  color: #64748b;
  margin: 0 0 32px 0;
  font-size: 16px;
  line-height: 1.5;
}

.empty-action-wrapper {
  display: flex;
  justify-content: center;
  width: 100%;
}

.empty-action {
  border-radius: 12px;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.empty-action:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(99, 102, 241, 0.3);
}

.button-icon {
  font-size: 18px;
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
  gap: 24px;
}

.model-info {
  flex: 1;
  min-width: 0;
}

.model-info h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  line-height: 32px;
}

.model-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  height: 32px;
}

.model-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.model-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 6px;
  width: 220px;
  flex-shrink: 0;
  margin-top: 0;
}

.action-btn {
  width: 100%;
  justify-content: center;
  font-weight: 500;
  border-radius: 8px;
  height: 32px;
  padding: 0 12px;
  transition: all 0.3s ease;
}

.action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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

/* 分析对话框样式 */
.dialog-loading {
  padding: 20px;
}

.session-list {
  max-height: 400px;
  overflow-y: auto;
}

.empty-sessions {
  text-align: center;
  padding: 40px 20px;
  color: #64748b;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  margin-bottom: 12px;
  background: rgba(248, 250, 252, 0.8);
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.6);
  transition: all 0.2s ease;
}

.session-item:hover {
  background: rgba(241, 245, 249, 1);
  transform: translateX(4px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.session-info {
  flex: 1;
}

.session-name {
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}

.session-meta {
  font-size: 13px;
  color: #64748b;
}

.dialog-footer {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
  display: flex;
  justify-content: center;
}
</style>
