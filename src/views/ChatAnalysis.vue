<script setup lang="ts">
import ChatInput from '@/components/chat/ChatInput.vue';
import ChatMessages from '@/components/chat/ChatMessages.vue';
import DatasetSelector from '@/components/chat/DatasetSelector.vue';
import FlowPanel from '@/components/chat/FlowPanel.vue';
import ModelSelectDialog from '@/components/chat/ModelSelectDialog.vue';
import ReportGenerationDialog from '@/components/chat/report/ReportGenerationDialog.vue';
import SessionEditDialog from '@/components/chat/SessionEditDialog.vue';
import SessionSidebar from '@/components/chat/SessionSidebar.vue';
import { useChat } from '@/composables/useChat';
import { useDataSourceStore } from '@/stores/datasource';
import { useMCPStore } from '@/stores/mcp';
import { useSessionStore } from '@/stores/session';
import type { MCPConnection, MLModel } from '@/types';
import { DArrowRight, Document, Monitor } from '@element-plus/icons-vue';
import { ElButton, ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import Model from '@/components/icons/Model.vue';

const router = useRouter();
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();
const mcpStore = useMCPStore();

// --- State for new UI ---
const isSidebarOpen = ref(true);
const userInput = ref<string>('');
const selectDatasetDialogVisible = ref<boolean>(false);
const isFlowPanelOpen = ref<boolean>(true); // 控制流程图面板的显示/隐藏
const chatMessagesRef = ref<InstanceType<typeof ChatMessages>>();
const flowPanelRef = ref<InstanceType<typeof FlowPanel>>();

// 当前会话的模型
const sessionModels = ref<MLModel[]>([]);

const sessions = computed(() => sessionStore.sessions);
const currentSessionId = computed(() => sessionStore.currentSessionId);
const currentDatasets = computed(() =>
  sessionStore.currentSession
    ? sessionStore.currentSession.dataset_ids
      .map(id => dataSourceStore.dataSources[id] || null).filter(ds => ds)
    : null
);

// 当前会话的MCP连接
const currentMCPConnections = ref<MCPConnection[]>([]);

// 加载当前会话的MCP连接
const loadCurrentMCPConnections = async () => {
  if (!currentSessionId.value) {
    currentMCPConnections.value = [];
    return;
  }

  try {
    const connections = await mcpStore.getSessionConnections(currentSessionId.value);
    currentMCPConnections.value = connections;
  } catch (error) {
    console.error('加载会话 MCP 连接失败:', error);
    currentMCPConnections.value = [];
  }
};

// 加载当前会话的模型
const loadCurrentSessionModels = async () => {
  if (!currentSessionId.value) {
    sessionModels.value = [];
    return;
  }

  try {
    const models = await sessionStore.getSessionModels(currentSessionId.value);
    sessionModels.value = models;
  } catch (error) {
    console.error('加载会话模型失败:', error);
    sessionModels.value = [];
  }
};

// 会话编辑相关
const editSessionDialogVisible = ref(false);
const editingSessionId = ref('');
const editingSessionName = ref('');

// 报告生成相关状态
const reportDialogVisible = ref(false);

const modelSelectDialogVisible = ref(false);

const {
  messages,
  isProcessingChat,
  ...chat
} = useChat(() => flowPanelRef.value?.flowPanel);

const openEditSessionDialog = (sessionId: string, sessionName: string) => {
  editingSessionId.value = sessionId;
  editingSessionName.value = sessionName;
  editSessionDialogVisible.value = true;
};

const saveSessionEdit = async () => {
  if (!editingSessionId.value || !editingSessionName.value.trim()) {
    ElMessage.warning('会话名称不能为空');
    return;
  }

  try {
    await sessionStore.updateSessionName(editingSessionId.value, editingSessionName.value.trim());
    ElMessage.success('会话名称更新成功');
    editSessionDialogVisible.value = false;
  } catch (error) {
    console.error('更新会话名称失败:', error);
    ElMessage.error('更新会话名称失败');
  }
};

const openReportDialog = async () => {
  if (!currentSessionId.value) {
    ElMessage.warning('请先选择一个会话');
    return;
  }

  if (messages.value.length === 0) {
    ElMessage.warning('当前会话没有分析内容');
    return;
  }

  reportDialogVisible.value = true;
};

const openModelSelectDialog = () => {
  modelSelectDialogVisible.value = true;
};

// --- Methods for new UI ---
const loadSessions = async () => {
  try {
    await sessionStore.listSessions();
  } catch (error) {
    console.error('加载会话失败:', error);
  }
};

const createNewSession = async (sourceIds: string[]) => {
  try {
    // 确保 sourceIds 是数组
    const datasetIds = Array.isArray(sourceIds) ? sourceIds : [sourceIds];

    // 如果数组为空，显示错误信息并退出
    if (datasetIds.length === 0) {
      ElMessage.warning('请至少选择一个数据集');
      return;
    }

    const session = await sessionStore.createSession(datasetIds);
    sessionStore.setCurrentSession(session);
    await refreshChatHistory();

    // 加载当前会话的MCP连接
    await loadCurrentMCPConnections();

    selectDatasetDialogVisible.value = false; // Close the dialog

    const message = datasetIds.length === 1
      ? '新对话创建成功'
      : `成功创建包含 ${datasetIds.length} 个数据集的对话`;

    ElMessage.success(message);
  } catch (error) {
    console.error('创建新会话失败:', error);
    ElMessage.error('创建新会话失败');
  }
};

const refreshChatHistory = async () => {
  if (!currentSessionId.value) return;
  await chat.refreshChatHistory(currentSessionId.value);
  nextTick(scrollToBottom);
};

const switchSession = async (sessionId: string) => {
  await sessionStore.setCurrentSessionById(sessionId);
  const session = sessions.value.find(s => s.id === sessionId);
  await refreshChatHistory();

  // 加载当前会话的MCP连接和模型
  await loadCurrentMCPConnections();
  await loadCurrentSessionModels();

  ElMessage.success(`切换到会话: ${session?.name || sessionId.slice(0, 8)}...`);
};

// 删除会话
const deleteSession = async (sessionId: string) => {
  const session = sessions.value.find(s => s.id === sessionId);
  const sessionName = session?.name || sessionId.slice(0, 8) + '...';

  try {
    await ElMessageBox.confirm(
      `确定要删除会话 "${sessionName}" 吗？删除后无法恢复。`,
      '删除会话',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    );

    await sessionStore.deleteSession(sessionId);

    // 如果删除的是当前会话
    if (sessionId === currentSessionId.value) {
      messages.value = [];
      flowPanelRef.value?.flowPanel?.clearFlowSteps();

      // 如果还有其他会话，切换到第一个会话
      if (sessions.value.length > 0) {
        await switchSession(sessions.value[0].id);
      }
    }

    ElMessage.success(`会话 "${sessionName}" 已删除`);

    // 如果没有会话了，提示用户创建新会话
    if (sessions.value.length === 0) {
      ElMessage.info('所有会话已删除，请创建新会话开始分析');
    }

  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除会话失败:', error);
      ElMessage.error('删除会话失败');
    }
  }
};

// --- Method to navigate to data management ---
const goToAddData = () => {
  router.push('/data-management');
};

// --- Existing Chat Logic Methods ---
const scrollToBottom = (): void => {
  chatMessagesRef.value?.scrollToBottom();
};

const sendMessage = async (): Promise<void> => {
  if (!userInput.value.trim()) return;
  const userMessage = userInput.value.trim();
  userInput.value = '';

  // 直接发送用户消息（模型提示已移至后端处理）
  await chat.sendMessage(
    userMessage,
    currentSessionId.value || null,
    currentDatasets.value,
    scrollToBottom,
  );
};

// --- Lifecycle Hooks ---
onMounted(async () => {
  await loadSessions();
  await dataSourceStore.listDataSources(); // 加载数据源
  await mcpStore.listConnections(); // 加载MCP连接

  if (currentSessionId.value) {
    await refreshChatHistory();
    await loadCurrentMCPConnections(); // 加载当前会话的MCP连接
    await loadCurrentSessionModels(); // 加载当前会话的模型
  }
});
</script>

<template>
  <div class="chat-analysis-container">

    <!-- Session Sidebar -->
    <SessionSidebar v-model:isSidebarOpen="isSidebarOpen"
      v-model:sessionMCPConnections="currentMCPConnections"
      @switch-session="switchSession"
      @create-session="selectDatasetDialogVisible = true"
      @edit-session="openEditSessionDialog"
      @delete-session="deleteSession" />

    <!-- Chat Panel -->
    <div class="chat-panel">
      <!-- Chat Panel Header -->
      <div class="chat-panel-header">
        <div class="header-left">
          <el-button v-if="!isSidebarOpen" @click="isSidebarOpen = true" :icon="DArrowRight" text class="toggle-btn" />
          <span class="session-title" v-if="currentSessionId">
            {{sessions.find(s => s.id === currentSessionId)?.name || `会话: ${currentSessionId.slice(0, 8)}...`}}
          </span>
        </div>
        <div class="header-right">
          <el-button v-if="currentSessionId" @click="openModelSelectDialog" :icon="Model"
            :type="sessionModels.length ? 'primary' : 'default'">
            {{ sessionModels?.length || 0 > 0 ? `已选择 ${sessionModels.length} 个模型` : '机器学习模型' }}
          </el-button>
          <el-button @click="openReportDialog" :icon="Document" text class="toggle-btn">
            生成报告
          </el-button>
          <el-button @click="isFlowPanelOpen = !isFlowPanelOpen" :icon="Monitor" text class="toggle-btn">
            流程图
          </el-button>
        </div>
      </div>

      <!-- Chat Messages Area -->
      <ChatMessages :messages="messages"
        :currentSessionId="currentSessionId"
        :currentDatasetExists="(currentDatasets?.length || 0) > 0"
        @add-sample-question="userInput = $event"
        ref="chatMessagesRef" />

      <!-- Chat Input Area -->
      <ChatInput v-model:input="userInput"
        :isProcessingChat="isProcessingChat"
        :currentDatasets="currentDatasets"
        :mcpConnections="currentMCPConnections"
        :sessionModels="sessionModels"
        @send="sendMessage"
        @go-to-data="goToAddData" />
    </div>

    <!-- Flow Panel -->
    <FlowPanel v-model:is-flow-panel-open="isFlowPanelOpen" ref="flowPanelRef" />

    <!-- Select Dataset Dialog -->
    <DatasetSelector v-model:visible="selectDatasetDialogVisible"
      @create-session="createNewSession"
      @go-to-data="goToAddData" />

    <!-- Session Edit Dialog -->
    <SessionEditDialog v-model:visible="editSessionDialogVisible"
      v-model:sessionName="editingSessionName"
      :sessionId="editingSessionId"
      @save="saveSessionEdit" />

    <!-- Report Generation Dialog -->
    <ReportGenerationDialog v-model:visible="reportDialogVisible" />

    <!-- Model Selection Dialog -->
    <ModelSelectDialog v-if="currentSessionId" v-model:visible="modelSelectDialogVisible"
      v-model:session-models="sessionModels" :current-session-id="currentSessionId" />
  </div>
</template>

<style lang="scss" scoped>
.chat-analysis-container {
  display: flex;
  height: calc(100vh - 80px);
  background-color: #ffffff;
}

// --- Chat Panel Styles ---
.chat-panel {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  position: relative;
  background: #ffffff;
}

.chat-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 45px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
  background: #ffffff;

  .header-left {
    display: flex;
    align-items: center;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .toggle-btn {
    color: #6b7280;
    padding: 8px;
    border-radius: 6px;
    transition: all 0.2s ease;

    &:hover {
      color: #374151;
      background-color: #f3f4f6;
    }
  }

  .session-title {
    font-weight: 600;
    margin-left: 12px;
    color: #1f2937;
    font-size: 16px;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .chat-analysis-container {
    flex-direction: column;
  }

  .session-sidebar {
    width: 100%;
    max-height: 200px;
    border-right: none;
    border-bottom: 1px solid #e5e7eb;

    &.is-closed {
      max-height: 0;
      overflow: hidden;
    }
  }

  .user-message {
    max-width: 85%;
  }

  .chat-input-area {
    padding: 12px 16px 16px;
  }

  .quick-actions {
    justify-content: flex-start;
  }

  .dataset-indicator {
    margin-right: 8px;
    margin-bottom: 8px;
  }
}

@keyframes pulse {

  0%,
  100% {
    transform: scale(1);
  }

  50% {
    transform: scale(1.05);
  }
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.rotating {
  animation: rotating 2s linear infinite;
}

/* 报告生成相关样式 */
.report-generation-options {
  margin-bottom: 24px;

  .template-selection {
    display: flex;
    gap: 16px;
    align-items: center;
    margin-bottom: 16px;
  }
}

.template-preview {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;

  h4 {
    margin: 0 0 8px 0;
    color: #374151;
    font-weight: 600;
  }

  p {
    margin: 0 0 16px 0;
    color: #6b7280;
    font-size: 14px;
  }

  .template-content {
    max-height: 300px;
    overflow-y: auto;

    pre {
      background: #f3f4f6;
      padding: 12px;
      border-radius: 6px;
      font-size: 12px;
      line-height: 1.5;
      margin: 0;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
  }
}

.template-management {
  .management-actions {
    margin-bottom: 16px;
  }
}

.report-preview-section {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;

  h3 {
    margin: 0 0 16px 0;
    color: #374151;
  }
}

.report-figures-section {
  margin-top: 24px;

  h3 {
    margin: 0 0 16px 0;
    color: #374151;
  }
}
</style>
