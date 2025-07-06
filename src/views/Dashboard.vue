<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAppStore } from '@/stores/app'
import type { Dataset, ChatEntry, AnalysisResult } from '@/types';

const appStore = useAppStore()

// 响应式数据
const currentDataset = ref<Dataset | null>(null)
const datasets = ref<Dataset[]>([])
const chatHistory = ref<ChatEntry[]>([])
const analysisResults = ref<AnalysisResult[]>([])
const recentActivity = ref<ChatEntry[]>([])

// 计算属性
const sessionInfo = computed<string>(() => {
  const sessionId = appStore.currentSessionId
  return sessionId ? `${sessionId.slice(0, 8)}...` : '无'
})

// 方法
const formatDate = (timestamp: string | undefined): string => {
  if (!timestamp) return '未知'
  const date = new Date(timestamp)
  return date.toLocaleString()
}

const loadData = async (): Promise<void> => {
  try {
    const session = appStore.currentSession
    if (session) {
      chatHistory.value = session.chat_history || []
      analysisResults.value = session.analysis_results || []
      recentActivity.value = session.chat_history || []

      if (session.current_dataset) {
        // 获取数据集信息
        const datasetsResponse = await appStore.getDatasets()
        datasets.value = datasetsResponse || []
        currentDataset.value = datasets.value.find(d => d.id === session.current_dataset) || null
      }
    }
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

// 生命周期
onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="dashboard">
    <!-- 欢迎信息 -->
    <div class="analysis-card welcome-card">
      <div class="card-header">
        <h2>
          <el-icon>
            <House />
          </el-icon>
          工作台总览
        </h2>
        <p class="subtitle">欢迎使用智能数据分析平台</p>
      </div>
      <el-row :gutter="24" class="stats-row">
        <el-col :span="6">
          <div class="stat-item">
            <el-statistic title="当前会话" :value="sessionInfo" />
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <el-statistic title="已上传数据集" :value="datasets.length" />
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <el-statistic title="分析会话" :value="chatHistory.length" />
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <el-statistic title="生成报告" :value="analysisResults.length" />
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 快速操作 -->
    <div class="analysis-card quick-actions-card">
      <h3>快速开始</h3>
      <p class="subtitle">选择一个操作开始您的数据分析之旅</p>
      <el-row :gutter="20" class="actions-row">
        <el-col :span="6">
          <div class="quick-action-card upload-card" @click="$router.push('/data-upload')">
            <div class="action-icon upload-icon">
              <el-icon>
                <Upload />
              </el-icon>
            </div>
            <h4>上传数据</h4>
            <p>支持 CSV、Excel 文件</p>
          </div>
        </el-col>

        <el-col :span="6">
          <div class="quick-action-card sources-card" @click="$router.push('/data-sources')">
            <div class="action-icon sources-icon">
              <el-icon>
                <Database />
              </el-icon>
            </div>
            <h4>连接数据源</h4>
            <p>连接 Dremio 等数据源</p>
          </div>
        </el-col>

        <el-col :span="6">
          <div class="quick-action-card chat-card" @click="$router.push('/chat-analysis')">
            <div class="action-icon chat-icon">
              <el-icon>
                <ChatDotRound />
              </el-icon>
            </div>
            <h4>对话分析</h4>
            <p>AI 驱动的数据对话</p>
          </div>
        </el-col>

        <el-col :span="6">
          <div class="quick-action-card analysis-card-action" @click="$router.push('/auto-analysis')">
            <div class="action-icon analysis-icon">
              <el-icon>
                <DataAnalysis />
              </el-icon>
            </div>
            <h4>自动分析</h4>
            <p>生成完整分析报告</p>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 当前数据集概览 -->
    <div class="analysis-card dataset-card" v-if="currentDataset">
      <h3>当前数据集</h3>
      <div class="dataset-overview">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="数据集名称">
            {{ currentDataset.name || '未命名' }}
          </el-descriptions-item>
          <el-descriptions-item label="数据行数">
            {{ currentDataset.overview?.shape ? currentDataset.overview?.shape[0] : 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="数据列数">
            {{ currentDataset.overview?.shape ? currentDataset.overview?.shape[1] : 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="上传时间">
            {{ formatDate(currentDataset?.created_at) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 最近活动 -->
    <div class="analysis-card recent-activity-card" v-if="recentActivity.length > 0">
      <h3>最近活动</h3>
      <div class="activity-list">
        <div v-for="activity in recentActivity.slice(0, 5)" :key="activity.timestamp" class="activity-item">
          <div class="activity-icon">
            <el-icon>
              <ChatDotRound />
            </el-icon>
          </div>
          <div class="activity-content">
            <p class="activity-title">{{ activity.user_message }}</p>
            <span class="activity-time">{{ formatDate(activity.timestamp) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 24px;
  min-height: 100vh;
}

.analysis-card {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(226, 232, 240, 0.8);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.welcome-card {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%);
}

.card-header h2 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 12px;
}

.subtitle {
  margin: 0;
  color: #64748b;
  font-size: 16px;
}

.stats-row {
  margin-top: 24px;
}

.stat-item {
  text-align: center;
  padding: 20px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.quick-actions-card h3 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1e293b;
}

.actions-row {
  margin-top: 24px;
}

.quick-action-card {
  text-align: center;
  padding: 32px 20px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid transparent;
  height: 100%;
}

.quick-action-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.15);
}

.upload-card:hover {
  border-color: #3b82f6;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(147, 197, 253, 0.1) 100%);
}

.sources-card:hover {
  border-color: #10b981;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(110, 231, 183, 0.1) 100%);
}

.chat-card:hover {
  border-color: #f59e0b;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%);
}

.analysis-card-action:hover {
  border-color: #ec4899;
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.1) 0%, rgba(244, 114, 182, 0.1) 100%);
}

.action-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  transition: all 0.3s ease;
}

.upload-icon {
  background: linear-gradient(135deg, #3b82f6 0%, #93c5fd 100%);
  color: white;
}

.sources-icon {
  background: linear-gradient(135deg, #10b981 0%, #6ee7b7 100%);
  color: white;
}

.chat-icon {
  background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
  color: white;
}

.analysis-icon {
  background: linear-gradient(135deg, #ec4899 0%, #f472b6 100%);
  color: white;
}

.quick-action-card h4 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.quick-action-card p {
  margin: 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.5;
}

.dataset-card h3,
.recent-activity-card h3 {
  margin: 0 0 20px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1e293b;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.activity-item:hover {
  background: rgba(255, 255, 255, 0.8);
  transform: translateX(4px);
}

.activity-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.activity-content {
  flex: 1;
}

.activity-title {
  margin: 0 0 4px 0;
  font-weight: 500;
  color: #1e293b;
  font-size: 14px;
}

.activity-time {
  color: #64748b;
  font-size: 12px;
}
</style>
