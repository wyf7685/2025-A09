<template>
  <div class="models-page">
    <div class="page-header">
      <div class="header-content">
        <h1>模型管理</h1>
        <p class="header-subtitle">管理您训练的机器学习模型</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshModels" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="models-content">
      <!-- 空状态 -->
      <div v-if="!loading && models.length === 0" class="empty-state">
        <el-empty 
          description="暂无训练模型"
          :image-size="120"
        >
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
        <el-card 
          v-for="model in models" 
          :key="model.id"
          class="model-card"
          shadow="hover"
        >
          <div class="model-header">
            <div class="model-info">
              <h3>{{ model.type }}</h3>
              <div class="model-meta">
                <span class="meta-item">
                  <el-icon><Calendar /></el-icon>
                  {{ formatDate(model.created_at) }}
                </span>
                <span class="meta-item">
                  <el-icon><DataAnalysis /></el-icon>
                  目标变量: {{ model.target }}
                </span>
                <span class="meta-item">
                  <el-icon><TrendCharts /></el-icon>
                  评分: {{ model.score.toFixed(3) }}
                </span>
              </div>
            </div>
            <div class="model-actions">
              <el-button size="small" @click="viewModel(model)">
                <el-icon><View /></el-icon>
                查看
              </el-button>
              <el-button size="small" type="danger" @click="deleteModel(model.id)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>
          
          <div class="model-features">
            <h4>特征变量</h4>
            <div class="features-list">
              <el-tag 
                v-for="feature in model.features.slice(0, 6)" 
                :key="feature"
                size="small"
                class="feature-tag"
              >
                {{ feature }}
              </el-tag>
              <el-tag 
                v-if="model.features.length > 6"
                size="small"
                type="info"
              >
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

    <!-- 模型详情对话框 -->
    <el-dialog 
      v-model="showModelDialog" 
      title="模型详情" 
      width="70%"
      class="model-dialog"
    >
      <div v-if="selectedModel" class="model-detail">
        <div class="detail-row">
          <label>模型类型:</label>
          <span>{{ selectedModel.type }}</span>
        </div>
        <div class="detail-row">
          <label>目标变量:</label>
          <span>{{ selectedModel.target }}</span>
        </div>
        <div class="detail-row">
          <label>模型评分:</label>
          <span>{{ selectedModel.score.toFixed(3) }}</span>
        </div>
        <div class="detail-row">
          <label>创建时间:</label>
          <span>{{ formatDate(selectedModel.created_at) }}</span>
        </div>
        <div class="detail-row">
          <label>特征变量:</label>
          <div class="features-grid">
            <el-tag 
              v-for="feature in selectedModel.features" 
              :key="feature"
              class="feature-tag"
            >
              {{ feature }}
            </el-tag>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const appStore = useAppStore()

// 响应式数据
const loading = ref(false)
const models = ref([])
const showModelDialog = ref(false)
const selectedModel = ref(null)

// 方法
const refreshModels = async () => {
  loading.value = true
  try {
    const sessionId = appStore.currentSessionId
    if (sessionId) {
      const response = await appStore.getModels(sessionId)
      models.value = response.models || []
    }
  } catch (error) {
    console.error('刷新模型失败:', error)
    ElMessage.error('获取模型列表失败')
  } finally {
    loading.value = false
  }
}

const formatDate = (timestamp) => {
  if (!timestamp) return '未知'
  const date = new Date(timestamp)
  return date.toLocaleString()
}

const viewModel = (model) => {
  selectedModel.value = model
  showModelDialog.value = true
}

const deleteModel = async (modelId) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个模型吗？此操作不可撤销。',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await appStore.deleteModel(modelId)
    await refreshModels()
    ElMessage.success('模型删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除模型失败:', error)
      ElMessage.error('删除模型失败')
    }
  }
}

// 生命周期
onMounted(() => {
  refreshModels()
})
</script>

<style scoped>
.models-page {
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 16px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.header-content h1 {
  margin: 0 0 8px 0;
  font-size: 32px;
  font-weight: 600;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.header-subtitle {
  margin: 0;
  color: #64748b;
  font-size: 16px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  backdrop-filter: blur(10px);
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
  border-radius: 6px;
}

.loading-state {
  padding: 24px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  backdrop-filter: blur(10px);
}

.model-detail {
  padding: 20px 0;
}

.detail-row {
  display: flex;
  margin-bottom: 20px;
  align-items: flex-start;
}

.detail-row label {
  width: 120px;
  font-weight: 500;
  color: #374151;
  flex-shrink: 0;
}

.detail-row span {
  color: #64748b;
}

.features-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}
</style>
