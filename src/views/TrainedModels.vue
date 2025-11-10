<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue';
import { useModelStore } from '@/stores/model';
import type { MLModel } from '@/types';
import { Calendar, DataAnalysis, Delete, Download, Refresh, Star, View } from '@element-plus/icons-vue';
import { Icon } from '@iconify/vue';
import { ElButton, ElCard, ElDialog, ElIcon, ElMessage, ElMessageBox, ElSkeleton, ElTag } from 'element-plus';
import { onMounted, ref } from 'vue';

const modelStore = useModelStore();

// 响应式数据
const loading = ref<boolean>(false);
const models = ref<MLModel[]>([]);
const showModelDialog = ref<boolean>(false);
const selectedModel = ref<MLModel | null>(null);

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

// 生命周期
onMounted(async () => {
  await refreshModels();
});
</script>

<template>
  <div class="trained-models-page">
    <div class="page-header">
      <PageHeader
        title="训练模型管理"
        subtitle="管理您在对话分析过程中训练的机器学习模型" />
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
              <el-button size="small" @click="modelStore.downloadModel(model.id)">
                <el-icon>
                  <Download />
                </el-icon>
                下载
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

.header-actions {
  display: flex;
  gap: 12px;
}

.models-container {
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
</style>
