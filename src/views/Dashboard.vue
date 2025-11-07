<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
import { useDataSourceStore } from '@/stores/datasource';
import { useSessionStore } from '@/stores/session';
import { Icon } from '@iconify/vue';
import { ElCol, ElRow, ElStatistic } from 'element-plus';
import { computed, onMounted } from 'vue';

const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();

// 计算属性
const currentSessionId = computed(() => sessionStore.currentSession?.id);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const currentSessionName = computed<any>(() => {
  if (!currentSessionId.value) return '无';
  const session = sessionStore.sessions.find(s => s.id === currentSessionId.value);
  const name = session?.name || (currentSessionId.value ? `${currentSessionId.value.slice(0, 8)}...` : '无');
  return name.length > 11 ? name.slice(0, 11) + '...' : name;
});
const dataSourceCount = computed(() => Object.keys(dataSourceStore.dataSources).length);
const chatHistoryLength = computed(() => sessionStore.currentSession?.chat_history.length || 0);

// 生命周期
onMounted(() => {
  sessionStore.listSessions().catch(error => {
    console.error('加载会话列表失败:', error);
  });
});
</script>

<template>
  <div class="dashboard">
    <!-- 欢迎信息 -->
    <div class="analysis-card welcome-card">
      <div class="card-header">
        <h2>
          <Icon icon="material-symbols:home-rounded" class="header-icon" />
          <span class="card-header-text"> 工作台总览</span>
        </h2>
        <p class="subtitle">欢迎使用智能数据分析平台</p>
      </div>
      <el-row :gutter="24" class="stats-row">
        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-icon session-icon">
              <Icon icon="material-symbols:chat-bubble-outline" />
            </div>
            <el-statistic title="当前会话" :value="currentSessionName" />
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-icon dataset-icon">
              <Icon icon="material-symbols:database-outline" />
            </div>
            <el-statistic title="已上传数据集" :value="dataSourceCount" />
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-icon history-icon">
              <Icon icon="material-symbols:history" />
            </div>
            <el-statistic title="分析会话" :value="chatHistoryLength" />
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 快速操作 -->
    <div class="analysis-card quick-actions-card">
      <div class="card-header">
        <h3>
          <Icon icon="heroicons:rocket-launch" class="section-icon" />
          <span class="card-header-text">快速开始</span>
        </h3>
        <p class="subtitle">选择一个操作开始您的数据分析之旅</p>
      </div>
      <el-row :gutter="24" class="actions-row">

        <el-col :span="8">
          <div class="quick-action-card sources-card" @click="$router.push('/data-management')">
            <div class="action-icon sources-icon">
              <Icon icon="material-symbols:storage" />
            </div>
            <h4>数据管理</h4>
            <p>管理您的数据源</p>
            <div class="card-arrow">
              <Icon icon="heroicons:arrow-right" />
            </div>
          </div>
        </el-col>

        <el-col :span="8">
          <div class="quick-action-card chat-card" @click="$router.push('/chat-analysis')">
            <div class="action-icon chat-icon">
              <Icon icon="material-symbols:smart-toy-outline" />
            </div>
            <h4>对话分析</h4>
            <p>智能数据分析助手</p>
            <div class="card-arrow">
              <Icon icon="heroicons:arrow-right" />
            </div>
          </div>
        </el-col>

        <el-col :span="8">
          <div class="quick-action-card upload-card" @click="$router.push('/data-upload')">
            <div class="action-icon upload-icon">
              <Icon icon="material-symbols:upload" />
            </div>
            <h4>数据上传</h4>
            <p>上传本地数据文件</p>
            <div class="card-arrow">
              <Icon icon="heroicons:arrow-right" />
            </div>
          </div>
        </el-col>

      </el-row>

      <!-- 模型管理区域 -->
      <div class="models-section">
        <h4 class="models-title">
          <Icon icon="material-symbols:psychology-alt-outline" class="models-icon" />
          模型管理
        </h4>
        <el-row :gutter="16" class="models-row">
          <el-col :span="12">
            <div class="quick-action-card models-card llm-card" @click="$router.push('/llm-models')">
              <div class="action-icon llm-icon">
                <Icon icon="material-symbols:neurology" />
              </div>
              <h5>大语言模型</h5>
              <p>管理 LLM 模型配置</p>
              <div class="card-arrow">
                <Icon icon="heroicons:arrow-right" />
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="quick-action-card models-card trained-card" @click="$router.push('/trained-models')">
              <div class="action-icon trained-icon">
                <Icon icon="material-symbols:model-training" />
              </div>
              <h5>训练模型</h5>
              <p>管理自训练模型</p>
              <div class="card-arrow">
                <Icon icon="heroicons:arrow-right" />
              </div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 高级功能区域 -->
      <div class="advanced-section">
        <h4 class="advanced-title">
          <Icon icon="material-symbols:settings-outline" class="advanced-icon" />
          高级功能
        </h4>
        <div class="quick-action-card advanced-card mcp-card" @click="$router.push('/mcp-connections')">
          <div class="action-icon mcp-icon">
            <Icon icon="material-symbols:hub-outline" />
          </div>
          <h5>MCP 连接管理</h5>
          <p>管理模型上下文协议连接</p>
          <div class="card-arrow">
            <Icon icon="heroicons:arrow-right" />
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
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: 2px solid rgba(226, 232, 240, 1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.analysis-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.3), transparent);
}

.welcome-card {
  background: #ffffff;
  border: 2px solid rgba(99, 102, 241, 0.3);
}

.card-header h2 {
  margin: 0 0 12px 0;
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 16px;
  letter-spacing: -0.02em;
}

.card-header-text {
  font-size: 28px;
}

.header-icon {
  font-size: 40px;
  color: #6366f1;
  filter: drop-shadow(0 2px 4px rgba(99, 102, 241, 0.2));
}

.section-icon {
  font-size: 28px;
  color: #e9580b;
}

.subtitle {
  margin: 0;
  color: #1e293b;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.6;
}

.stats-row {
  margin-top: 32px;
}

.stat-item {
  position: relative;
  text-align: center;
  padding: 20px 16px;
  background: #ffffff;
  border-radius: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid rgba(226, 232, 240, 0.8);
  overflow: hidden;
}

.stat-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  transform: scaleX(0);
  transition: transform 0.3s ease;
}

.stat-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.12);
  border-color: rgba(99, 102, 241, 0.3);
}

.stat-item:hover::before {
  transform: scaleX(1);
}

.stat-icon {
  width: 40px;
  height: 40px;
  margin: 0 auto 12px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  position: relative;
  transition: all 0.3s ease;
}

.session-icon {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  color: white;
  box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
}

.dataset-icon {
  background: linear-gradient(135deg, #10b981 0%, #047857 100%);
  color: white;
  box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
}

.history-icon {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
  box-shadow: 0 4px 8px rgba(245, 158, 11, 0.3);
}

.quick-actions-card h3 {
  margin: 0 0 12px 0;
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 12px;
  letter-spacing: -0.02em;
}

.actions-row {
  margin-top: 24px;
}

.quick-action-card {
  position: relative;
  text-align: center;
  padding: 24px 20px;
  background: #ffffff;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid rgba(226, 232, 240, 0.8);
  height: auto;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
}

.quick-action-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, transparent, currentColor, transparent);
  transform: scaleX(0);
  transition: transform 0.3s ease;
}

.quick-action-card:hover {
  transform: translateY(-4px) scale(1.01);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.12);
}

.quick-action-card:hover::before {
  transform: scaleX(1);
}

.upload-card {
  border-color: rgba(59, 130, 246, 0.3);
}

.upload-card:hover {
  border-color: #3b82f6;
  background: #ffffff;
  color: #3b82f6;
  box-shadow: 0 12px 24px rgba(59, 130, 246, 0.15);
}

.sources-card {
  border-color: rgba(16, 185, 129, 0.3);
}

.sources-card:hover {
  border-color: #10b981;
  background: #ffffff;
  color: #10b981;
  box-shadow: 0 12px 24px rgba(16, 185, 129, 0.15);
}

.chat-card {
  border-color: rgba(245, 158, 11, 0.3);
}

.chat-card:hover {
  border-color: #f59e0b;
  background: #ffffff;
  color: #f59e0b;
  box-shadow: 0 12px 24px rgba(245, 158, 11, 0.15);
}

.action-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 16px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.action-icon::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.2);
  border-radius: inherit;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.quick-action-card:hover .action-icon::before {
  opacity: 1;
}

.upload-icon {
  background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
  color: white;
  box-shadow: 0 6px 12px rgba(59, 130, 246, 0.3);
}

.sources-icon {
  background: linear-gradient(135deg, #10b981 0%, #047857 100%);
  color: white;
  box-shadow: 0 6px 12px rgba(16, 185, 129, 0.3);
}

.chat-icon {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
  box-shadow: 0 6px 12px rgba(245, 158, 11, 0.3);
}

.llm-icon {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  color: white;
  box-shadow: 0 6px 12px rgba(139, 92, 246, 0.3);
}

.trained-icon {
  background: linear-gradient(135deg, #ec4899 0%, #db2777 100%);
  color: white;
  box-shadow: 0 6px 12px rgba(236, 72, 153, 0.3);
}

.mcp-icon {
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  color: white;
  box-shadow: 0 6px 12px rgba(6, 182, 212, 0.3);
}

.quick-action-card h4 {
  margin: 0 0 12px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  letter-spacing: -0.01em;
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.quick-action-card h5 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  letter-spacing: -0.01em;
}

.quick-action-card p {
  margin: 0;
  color: #1e293b;
  font-size: 15px;
  line-height: 1.6;
  font-weight: 500;
}

.card-arrow {
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 20px;
  color: #1e293b;
  transition: all 0.3s ease;
  opacity: 0;
  transform: translateX(-8px);
}

.quick-action-card:hover .card-arrow {
  opacity: 1;
  transform: translateX(0);
  color: currentColor;
}

/* 模型管理区域 */
.models-section {
  margin-top: 40px;
  padding-top: 32px;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
}

.models-title {
  margin: 0 0 24px 0;
  font-size: 22px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 12px;
}

.models-icon {
  font-size: 24px;
  color: #8b5cf6;
}

.models-row {
  margin-top: 16px;
}

.models-card {
  min-height: 140px;
  padding: 20px 16px;
}

.models-card .action-icon {
  width: 50px;
  height: 50px;
  font-size: 24px;
  margin-bottom: 12px;
}

.llm-card {
  border-color: rgba(139, 92, 246, 0.3);
}

.llm-card:hover {
  border-color: #8b5cf6;
  background: #ffffff;
  color: #8b5cf6;
  box-shadow: 0 12px 24px rgba(139, 92, 246, 0.15);
}

.trained-card {
  border-color: rgba(236, 72, 153, 0.3);
}

.trained-card:hover {
  border-color: #ec4899;
  background: #ffffff;
  color: #ec4899;
  box-shadow: 0 12px 24px rgba(236, 72, 153, 0.15);
}

/* 高级功能区域 */
.advanced-section {
  margin-top: 32px;
  padding-top: 32px;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
}

.advanced-title {
  margin: 0 0 20px 0;
  font-size: 22px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 12px;
}

.advanced-icon {
  font-size: 24px;
  color: #06b6d4;
}

.advanced-card {
  min-height: 120px;
  padding: 20px;
  max-width: 400px;
}

.advanced-card .action-icon {
  width: 50px;
  height: 50px;
  font-size: 24px;
  margin-bottom: 12px;
}

.mcp-card {
  border-color: rgba(6, 182, 212, 0.3);
}

.mcp-card:hover {
  border-color: #06b6d4;
  background: #ffffff;
  color: #06b6d4;
  box-shadow: 0 12px 24px rgba(6, 182, 212, 0.15);
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .actions-row .el-col {
    margin-bottom: 16px;
  }

  .models-row .el-col {
    margin-bottom: 16px;
  }
}

@media (max-width: 768px) {
  .dashboard {
    padding: 16px;
  }

  .analysis-card {
    padding: 24px;
    margin-bottom: 24px;
  }

  .card-header h2 {
    font-size: 24px;
  }

  .quick-actions-card h3 {
    font-size: 20px;
  }

  .action-icon {
    width: 60px;
    height: 60px;
    font-size: 28px;
  }
}
</style>
