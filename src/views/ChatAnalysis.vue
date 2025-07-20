<script setup lang="ts">
import ChatInput from '@/components/chat/ChatInput.vue';
import ChatMessages from '@/components/chat/ChatMessages.vue';
import DatasetSelector from '@/components/chat/DatasetSelector.vue';
import FlowPanel from '@/components/chat/FlowPanel.vue';
import SessionEditDialog from '@/components/chat/SessionEditDialog.vue';
import SessionSidebar from '@/components/chat/SessionSidebar.vue';
import { useChat } from '@/composables/useChat';
import { useDataSourceStore } from '@/stores/datasource';
import { useSessionStore } from '@/stores/session';
import { DArrowRight, Monitor, Document } from '@element-plus/icons-vue';
import { ElButton, ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { reportAPI } from '@/utils/api';
import type { ReportTemplate } from '@/types/report';

const router = useRouter();
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();

// --- State for new UI ---
const isSidebarOpen = ref(true);
const userInput = ref<string>('');
const selectDatasetDialogVisible = ref<boolean>(false);
const isFlowPanelOpen = ref<boolean>(true); // 控制流程图面板的显示/隐藏
const chatMessagesRef = ref<InstanceType<typeof ChatMessages>>();
const flowPanelRef = ref<InstanceType<typeof FlowPanel>>();

const sessions = computed(() => sessionStore.sessions);
const currentSessionId = computed(() => sessionStore.currentSessionId);
const currentDatasets = computed(() =>
  sessionStore.currentSession
    ? sessionStore.currentSession.dataset_ids
      .map(id => dataSourceStore.dataSources[id] || null).filter(ds => ds)
    : null
);

// 报告生成相关状态
const reportDialogVisible = ref(false);
const isGeneratingReport = ref(false);
const reportTemplates = ref<ReportTemplate[]>([]);
const selectedTemplateId = ref<string>('default');
const generatedReport = ref<string>('');
const reportFigures = ref<string[]>([]);
const activeTab = ref('generate');
const viewingTemplate = ref<any>(null);

// 模板上传相关
const uploadTemplateDialogVisible = ref(false);
const templateName = ref('');
const templateDescription = ref('');
const templateContent = ref('');

// 会话编辑相关
const editSessionDialogVisible = ref(false);
const editingSessionId = ref('');
const editingSessionName = ref('');

const {
  messages,
  isProcessingChat,
  ...chat
} = useChat(() => flowPanelRef.value?.flowPanel);

// 报告生成相关方法
const loadReportTemplates = async () => {
  try {
    const result = await reportAPI.getTemplates();
    reportTemplates.value = result;
  } catch (error) {
    console.error('加载报告模板失败:', error);
    ElMessage.error('加载报告模板失败');
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

  // 重置状态
  activeTab.value = 'generate';
  viewingTemplate.value = null;
  generatedReport.value = '';
  reportFigures.value = [];

  await loadReportTemplates();
  reportDialogVisible.value = true;
};

const generateReport = async () => {
  if (!currentSessionId.value) return;

  isGeneratingReport.value = true;
  try {
    // 统一使用报告生成接口
    const result = await reportAPI.generateReport(
      currentSessionId.value,
      selectedTemplateId.value === 'default' ? undefined : selectedTemplateId.value
    );
    generatedReport.value = result.report;
    reportFigures.value = result.figures;
    ElMessage.success(`报告生成成功！使用模板：${result.template_used}`);
  } catch (error: any) {
    console.error('生成报告失败:', error);
    ElMessage.error('生成报告失败: ' + (error?.response?.data?.detail || error?.message || error));
  } finally {
    isGeneratingReport.value = false;
  }
};

const downloadReport = () => {
  if (!generatedReport.value) return;

  const sessionName = sessions.value.find(s => s.id === currentSessionId.value)?.name || '未命名会话';
  const filename = `${sessionName}_分析报告_${new Date().toISOString().slice(0, 10)}.md`;

  reportAPI.downloadReport(generatedReport.value, filename);
  ElMessage.success('报告下载成功');
};

const viewSelectedTemplate = () => {
  const template = reportTemplates.value.find(t => t.id === selectedTemplateId.value);
  if (template) {
    viewingTemplate.value = template;
  } else if (selectedTemplateId.value === 'default') {
    // 从模板列表中找到默认模板
    const defaultTemplate = reportTemplates.value.find(t => t.is_default);
    if (defaultTemplate) {
      viewingTemplate.value = defaultTemplate;
    } else {
      // 如果没有找到，显示占位符
      viewingTemplate.value = {
        name: '默认分析报告模板',
        description: '系统内置的标准数据分析报告模板',
        content: '正在加载默认模板内容...'
      };
    }
  }
};

const viewTemplate = (template: any) => {
  viewingTemplate.value = template;
};

const deleteTemplate = async (templateId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除这个模板吗？', '删除确认', {
      type: 'warning'
    });

    await reportAPI.deleteTemplate(templateId);
    ElMessage.success('模板删除成功');
    await loadReportTemplates();
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除模板失败:', error);
      ElMessage.error('删除模板失败');
    }
  }
};

const openUploadTemplate = () => {
  templateName.value = '';
  templateDescription.value = '';
  templateContent.value = '';
  uploadTemplateDialogVisible.value = true;
};

const uploadTemplate = async () => {
  if (!templateName.value.trim() || !templateDescription.value.trim() || !templateContent.value.trim()) {
    ElMessage.warning('请填写完整的模板信息');
    return;
  }

  try {
    const blob = new Blob([templateContent.value], { type: 'text/plain' });
    const file = new File([blob], `${templateName.value}.txt`, { type: 'text/plain' });

    await reportAPI.uploadTemplate(templateName.value, templateDescription.value, file);
    ElMessage.success('模板上传成功');

    uploadTemplateDialogVisible.value = false;
    await loadReportTemplates();
  } catch (error: any) {
    console.error('上传模板失败:', error);
    ElMessage.error('上传模板失败: ' + (error?.message || error));
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
  } catch (error) {
    console.error('更新会话名称失败:', error);
    ElMessage.error('更新会话名称失败');
  }
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

  await chat.sendMessage(
    userMessage,
    currentSessionId.value,
    currentDatasets.value,
    scrollToBottom
  );
};

// --- Lifecycle Hooks ---
onMounted(async () => {
  await loadSessions();
  await dataSourceStore.listDataSources(); // 加载数据源
  if (currentSessionId.value) {
    refreshChatHistory();
  }
});
</script>

<template>
  <div class="chat-analysis-container">

    <!-- Session Sidebar -->
    <SessionSidebar v-model:isSidebarOpen="isSidebarOpen" :currentSessionId="currentSessionId"
      @switch-session="switchSession" @create-session="selectDatasetDialogVisible = true"
      @edit-session="openEditSessionDialog" @delete-session="deleteSession" />

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
          <el-button @click="openReportDialog" :icon="Document" text class="toggle-btn">
            生成报告
          </el-button>
          <el-button @click="isFlowPanelOpen = !isFlowPanelOpen" :icon="Monitor" text class="toggle-btn">
            流程图
          </el-button>
        </div>
      </div>

      <!-- Chat Messages Area -->
      <ChatMessages :messages="messages" :currentSessionId="currentSessionId"
        :currentDatasetExists="(currentDatasets?.length || 0) > 0" @add-sample-question="userInput = $event"
        ref="chatMessagesRef" />

      <!-- Chat Input Area -->
      <ChatInput v-model:input="userInput" :isProcessingChat="isProcessingChat" :currentDatasets="currentDatasets"
        @send="sendMessage" @go-to-data="goToAddData" />
    </div>

    <!-- Flow Panel -->
    <FlowPanel v-model:is-flow-panel-open="isFlowPanelOpen" ref="flowPanelRef"></FlowPanel>

    <!-- Select Dataset Dialog -->
    <DatasetSelector v-model:visible="selectDatasetDialogVisible" @create-session="createNewSession"
      @go-to-data="goToAddData" />

    <!-- Session Edit Dialog -->
    <SessionEditDialog v-model:visible="editSessionDialogVisible" v-model:sessionName="editingSessionName"
      :sessionId="editingSessionId" @save="saveSessionEdit" />

    <!-- 报告生成对话框 -->
    <ElDialog v-model="reportDialogVisible" title="生成分析报告" width="80%" :close-on-click-modal="false"
      :close-on-press-escape="false">
      <el-tabs v-model="activeTab">
        <!-- 生成报告选项卡 -->
        <el-tab-pane label="生成报告" name="generate">
          <div class="report-generation-options">
            <div class="template-selection">
              <el-select v-model="selectedTemplateId" placeholder="选择报告模板" style="width: 300px;">
                <el-option label="默认模板" value="default"></el-option>
                <el-option v-for="template in reportTemplates.filter(t => !t.is_default)" :key="template.id"
                  :label="template.name" :value="template.id"></el-option>
              </el-select>
              <el-button @click="viewSelectedTemplate" :disabled="!selectedTemplateId">
                查看模板
              </el-button>
              <el-button type="primary" :loading="isGeneratingReport" @click="generateReport">
                生成报告
              </el-button>
            </div>
          </div>

          <!-- 模板预览 -->
          <div v-if="viewingTemplate" class="template-preview">
            <h4>{{ viewingTemplate.name }}</h4>
            <p>{{ viewingTemplate.description }}</p>
            <div class="template-content">
              <pre>{{ viewingTemplate.content }}</pre>
            </div>
          </div>
        </el-tab-pane>

        <!-- 模板管理选项卡 -->
        <el-tab-pane label="模板管理" name="manage">
          <div class="template-management">
            <div class="management-actions">
              <el-button type="primary" @click="openUploadTemplate">
                <el-icon>
                  <Upload />
                </el-icon>
                上传新模板
              </el-button>
            </div>

            <el-table :data="reportTemplates" style="width: 100%; margin-top: 16px;">
              <el-table-column prop="name" label="模板名称" width="200"></el-table-column>
              <el-table-column prop="description" label="描述"></el-table-column>
              <el-table-column label="类型" width="100">
                <template #default="scope">
                  <el-tag :type="scope.row.is_default ? 'info' : 'success'">
                    {{ scope.row.is_default ? '系统' : '自定义' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150">
                <template #default="scope">
                  <el-button type="text" @click="viewTemplate(scope.row)">查看</el-button>
                  <el-button v-if="!scope.row.is_default" type="text" @click="deleteTemplate(scope.row.id)"
                    style="color: #f56c6c;">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>

      <div v-if="generatedReport" class="report-preview-section">
        <h3>报告预览</h3>
        <div class="markdown-content">
          <pre style="white-space: pre-wrap; font-family: inherit;">{{ generatedReport }}</pre>
        </div>
      </div>

      <div v-if="reportFigures.length > 0" class="report-figures-section">
        <h3>报告图表</h3>
        <div v-for="(figure, index) in reportFigures" :key="index">
          <img :src="`data:image/png;base64,${figure}`" alt="报告图表"
            style="max-width: 100%; height: auto; margin-bottom: 10px;">
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="reportDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="downloadReport" :disabled="!generatedReport">
            <el-icon>
              <Download />
            </el-icon>
            下载报告
          </el-button>
        </span>
      </template>
    </ElDialog>

    <!-- 模板上传对话框 -->
    <ElDialog v-model="uploadTemplateDialogVisible" title="上传报告模板" width="60%" :close-on-click-modal="false"
      :close-on-press-escape="false">
      <el-form label-width="120px">
        <el-form-item label="模板名称">
          <el-input v-model="templateName" placeholder="请输入模板名称"></el-input>
        </el-form-item>
        <el-form-item label="模板描述">
          <el-input v-model="templateDescription" type="textarea" placeholder="请输入模板描述"></el-input>
        </el-form-item>
        <el-form-item label="模板内容">
          <el-input v-model="templateContent" type="textarea" placeholder="请输入模板内容，使用 {conversation} 作为对话内容的占位符"
            :rows="10"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="uploadTemplateDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="uploadTemplate">上传</el-button>
        </span>
      </template>
    </ElDialog>
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
  height: 60px;
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
