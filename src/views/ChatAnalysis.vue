<script setup lang="ts">
import ChatInput from '@/components/chat/ChatInput.vue';
import ChatMessages from '@/components/chat/ChatMessages.vue';
import DatasetSelector from '@/components/chat/DatasetSelector.vue';
import ModelSelectDialog from '@/components/chat/ModelSelectDialog.vue';
import ReportGenerationDialog from '@/components/chat/report/ReportGenerationDialog.vue';
import SessionEditDialog from '@/components/chat/SessionEditDialog.vue';
import SessionSidebar from '@/components/chat/SessionSidebar.vue';
import Model from '@/components/icons/Model.vue';
import SaveWorkflowDialog from '@/components/workflow/SaveWorkflowDialog.vue';
import WorkflowManager from '@/components/workflow/WorkflowManager.vue';
import { useChat } from '@/composables/useChat';
import { useDataSourceStore } from '@/stores/datasource';
import { useMCPStore } from '@/stores/mcp';
import { useSessionStore } from '@/stores/session';
import type { AssistantChatMessage, MCPConnection, MLModel } from '@/types';
import { API_BASE_URL } from '@/utils/api';
import { persistConfig } from '@/utils/tools';
import { Document, DocumentAdd, Share } from '@element-plus/icons-vue';
import { ElButton, ElMessage, ElMessageBox, ElTooltip } from 'element-plus';
import { computed, nextTick, onErrorCaptured, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const router = useRouter();
const route = useRoute();
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();
const mcpStore = useMCPStore();

// 添加全局错误处理
onErrorCaptured((err) => {
  console.error('Captured error in ChatAnalysis:', err);
  ElMessage.error('对话分析组件发生错误，请刷新页面或联系管理员');
  return false; // 阻止错误继续传播
});

// --- State for new UI ---
const isSidebarOpen = persistConfig('chat-sidebar-open', true);
const userInput = ref<string>('');
const selectDatasetDialogVisible = ref<boolean>(false);
const chatMessagesRef = ref<InstanceType<typeof ChatMessages>>();

// 当前会话的模型
const sessionModels = ref<MLModel[]>([]);

// --- 工作流相关 ---
const saveWorkflowDialogVisible = ref(false);
const workflowManagerDialogVisible = ref(false);

const sessions = computed(() => sessionStore.sessions);
const currentSessionId = computed(() => sessionStore.currentSessionId);
const currentSessionName = computed(() => sessionStore.currentSessionName);
const currentDatasetMetadatas = computed(() =>
  sessionStore.currentSession
    ? sessionStore.currentSession.dataset_ids
      .map(id => dataSourceStore.dataSources[id] || null).filter(ds => ds)
    : null
);
const currentDatasets = computed(() =>
  sessionStore.currentSession
    ? sessionStore.currentSession.dataset_ids
      .map(id => { return { id, name: dataSourceStore.dataSources[id]?.name || "unknown" }; })
    : []
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
} = useChat();

// 打开保存工作流对话框
const openSaveWorkflowDialog = () => {
  if (!currentSessionId.value) {
    ElMessage.warning('请先创建或选择一个会话');
    return;
  }

  if (messages.value.length === 0) {
    ElMessage.warning('当前会话没有任何消息，无法保存工作流');
    return;
  }

  // 检查是否有工具调用
  let hasToolCalls = false;
  for (const message of messages.value) {
    if (message.type === 'assistant' && message.tool_calls && Object.keys(message.tool_calls).length > 0) {
      hasToolCalls = true;
      break;
    }
  }

  if (!hasToolCalls) {
    ElMessageBox.confirm(
      '当前会话中没有检测到工具调用，保存的工作流将无法执行任何操作。确定要继续吗？',
      '无工具调用提示',
      {
        confirmButtonText: '继续保存',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      saveWorkflowDialogVisible.value = true;
    }).catch(() => { });
  } else {
    saveWorkflowDialogVisible.value = true;
  }
};

// 打开工作流管理对话框
const openWorkflowManager = () => {
  if (!currentSessionId.value) {
    ElMessage.warning('请先创建或选择一个会话');
    return;
  }

  workflowManagerDialogVisible.value = true;
};

// 工作流保存成功回调
const onWorkflowSaved = () => {
  ElMessage.success('工作流保存成功');
  saveWorkflowDialogVisible.value = false;
};

// 工作流执行成功回调
const onWorkflowExecuting = async (payload: {
  workflow_id: string;
  workflow_name: string;
  session_id: string;
  datasource_mappings: Record<string, string>;
  message: string;
}) => {
  console.log('开始执行工作流:', payload);

  // 关闭工作流管理对话框
  workflowManagerDialogVisible.value = false;

  // 使用 EventSource 处理流式响应
  const url = `${API_BASE_URL}/workflow/execute`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        workflow_id: payload.workflow_id,
        session_id: payload.session_id,
        datasource_mappings: payload.datasource_mappings,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // 添加用户消息
    messages.value.push({
      type: 'user',
      content: payload.message,
      timestamp: new Date().toISOString(),
    });

    // 创建助手消息用于显示执行过程
    const assistantMessage = reactive({
      type: 'assistant',
      content: [],
      timestamp: new Date().toISOString(),
      tool_calls: {},
      loading: true,
      suggestions: [],
    } as AssistantChatMessage & { loading: boolean; tool_calls: NonNullable<AssistantChatMessage["tool_calls"]>; });

    messages.value.push(assistantMessage);
    scrollToBottom();

    // 处理流式响应
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('无法获取响应流');
    }

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.trim()) continue;

        try {
          const event = JSON.parse(line);

          // 处理不同类型的事件
          if (event.type === 'llm_token') {
            const content = event.content;
            if (
              !assistantMessage.content.length ||
              assistantMessage.content[assistantMessage.content.length - 1].type !== 'text'
            ) {
              assistantMessage.content.push({ type: 'text', content });
            }
            const lastText = assistantMessage.content[assistantMessage.content.length - 1] as {
              content: string;
            };
            lastText.content += content;
          } else if (event.type === 'tool_call') {
            // 工具调用开始
            const toolCallId = event.id;
            assistantMessage.content.push({
              type: 'tool_call',
              id: toolCallId,
            });
            assistantMessage.tool_calls[toolCallId] = {
              name: event.human_repr,
              args: JSON.stringify(event.args),
              status: 'running',
            };
          } else if (event.type === 'tool_result') {
            // 工具执行成功
            const toolCallId = event.id;
            if (assistantMessage.tool_calls[toolCallId]) {
              assistantMessage.tool_calls[toolCallId].status = 'success';
              assistantMessage.tool_calls[toolCallId].result = event.result;

              // 如果有图像 artifact，添加到内容中
              if (event.artifact && event.artifact.type === 'image') {
                const imageBase64 = event.artifact.base64_data;
                const caption = event.artifact.caption || '分析结果图表';
                const imageMarkdown = `\n\n![${caption}](data:image/png;base64,${imageBase64})`;
                assistantMessage.tool_calls[toolCallId].result += imageMarkdown;
              }
            }
          } else if (event.type === 'tool_error') {
            // 工具执行失败
            const toolCallId = event.id;
            if (assistantMessage.tool_calls[toolCallId]) {
              assistantMessage.tool_calls[toolCallId].status = 'error';
              assistantMessage.tool_calls[toolCallId].error = event.error;
            }
          } else if (event.type === 'done') {
            // 执行完成
            assistantMessage.loading = false;
          } else if (event.error) {
            // 错误
            ElMessage.error(`工作流执行失败: ${event.error}`);
            assistantMessage.loading = false;
          }

          scrollToBottom();
        } catch (e) {
          console.error('解析事件失败:', e, line);
        }
      }
    }

    assistantMessage.loading = false;
    scrollToBottom();

    // 刷新聊天历史
    await refreshChatHistory();
    await sessionStore.refreshSessionName(payload.session_id);

    ElMessage.success('工作流执行完成');
  } catch (error) {
    console.error('执行工作流失败:', error);
    ElMessage.error(`执行工作流失败: ${error}`);
  }
};

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
    await sessionStore.refreshSessionName(editingSessionId.value);
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

const openModelSelectDialog = async () => {
  // 在打开对话框前先加载当前会话的模型
  await loadCurrentSessionModels();
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

  await chat.sendMessage(
    userMessage,
    currentSessionId.value || null,
    currentDatasetMetadatas.value,
    scrollToBottom,
  );
};

// --- Lifecycle Hooks ---
onMounted(async () => {
  await loadSessions();
  await dataSourceStore.listDataSources(); // 加载数据源
  await mcpStore.listConnections(); // 加载MCP连接

  // 检查URL参数中的session ID
  const sessionFromUrl = route.query.session as string;
  if (sessionFromUrl) {
    // 如果URL中有session参数，切换到该会话
    await switchSession(sessionFromUrl);
  } else if (currentSessionId.value) {
    // 如果没有URL参数但有当前会话，加载当前会话的数据
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
          <!-- 会话标题 -->
          <el-tooltip :content="currentSessionName" placement="bottom">
            <span class="session-title" v-if="currentSessionId">
              {{ currentSessionName }}
            </span>
          </el-tooltip>
        </div>
        <div class="header-right">
          <el-button v-if="currentSessionId" @click="openModelSelectDialog" :icon="Model"
            :type="sessionModels.length ? 'primary' : 'default'">
            {{ sessionModels?.length || 0 > 0 ? `已选择 ${sessionModels.length} 个模型` : '机器学习模型' }}
          </el-button>
          <el-button @click="openSaveWorkflowDialog" :icon="DocumentAdd" class="workflow-btn">
            保存流程
          </el-button>
          <el-button @click="openWorkflowManager" :icon="Share" class="workflow-btn">
            调用流程
          </el-button>
          <el-button @click="openReportDialog" :icon="Document" text class="workflow-btn">
            生成报告
          </el-button>
        </div>
      </div>

      <!-- Chat Messages Area -->
      <ChatMessages :messages="messages"
        :currentSessionId="currentSessionId"
        :currentDatasetExists="(currentDatasetMetadatas?.length || 0) > 0"
        @add-sample-question="userInput = $event"
        ref="chatMessagesRef" />

      <!-- Chat Input Area -->
      <ChatInput v-model:input="userInput"
        :isProcessingChat="isProcessingChat"
        :currentDatasets="currentDatasetMetadatas"
        :mcpConnections="currentMCPConnections"
        :sessionModels="sessionModels"
        @send="sendMessage"
        @go-to-data="goToAddData" />
    </div>


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
      v-model:session-models="sessionModels" :current-session-id="currentSessionId"
      @models-updated="loadCurrentSessionModels" />

    <!-- 保存工作流对话框 -->
    <SaveWorkflowDialog
      v-model:visible="saveWorkflowDialogVisible"
      :messages="messages"
      :sessionId="currentSessionId || ''"
      @saved="onWorkflowSaved" />

    <!-- 工作流管理对话框 -->
    <WorkflowManager
      v-model:visible="workflowManagerDialogVisible"
      :selectionMode="true"
      :sessionId="currentSessionId || ''"
      :dataSources="currentDatasets"
      @workflowExecuting="onWorkflowExecuting" />
  </div>
</template>

<style lang="scss" scoped>
.chat-analysis-container {
  display: flex;
  height: 100vh;
  background-color: #ffffff;
  margin: -16px;
  /* 抵消 layout-content 的 padding */
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
  overflow: hidden;
  /* 防止内容溢出 */
}

.chat-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  /* 修改为与 SessionSidebar 一致的内边距 */
  height: 56px;
  /* 固定高度与 SessionSidebar 保持一致 */
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
    max-height: 1.2rem;
    overflow: hidden;
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

.workflow-btn {
  margin-right: 8px;
  font-size: 13px;
  border: 1px solid #dcdfe6;

  &:hover {
    color: var(--el-color-primary);
    border-color: var(--el-color-primary-light-7);
    background-color: var(--el-color-primary-light-9);
  }

  .icon-margin {
    margin-right: 4px;
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
