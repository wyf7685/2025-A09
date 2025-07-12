<script setup lang="ts">
import type { AssistantChatMessage, ChatEntry, ChatMessage } from '@/types';
import { ElMessage } from 'element-plus';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import AssistantMessage from '@/components/AssistantMessage.vue';
import { useSessionStore } from '@/stores/session';
import { useDataSourceStore } from '@/stores/datasource';
import { Plus, ChatDotRound, Delete, Edit, DArrowLeft, DArrowRight, DocumentCopy, WarningFilled, DataAnalysis, PieChart, Search, Document } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router';

type ChatMessageWithSuggestions = ChatMessage & { suggestions?: string[] }

const router = useRouter()
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();

// --- State for new UI ---
const isSidebarOpen = ref(true)

const userInput = ref<string>('')
const messages = ref<ChatMessageWithSuggestions[]>([])
const messagesContainer = ref<HTMLElement | null>(null)
const isProcessingChat = ref<boolean>(false)
const selectDatasetDialogVisible = ref<boolean>(false)

const sessions = computed(() => sessionStore.sessions)
const currentSessionId = computed(() => sessionStore.currentSession?.id)
const currentDataset = computed(() =>
  sessionStore.currentSession
    ? dataSourceStore.dataSources[sessionStore.currentSession.dataset_id]
    : null
);

// --- Methods for new UI ---
const loadSessions = async () => {
  try {
    await sessionStore.listSessions()
  } catch (error) {
    console.error('加载会话失败:', error)
  }
}

const createNewSession = async (sourceId: string) => {
  try {
    const session = await sessionStore.createSession(sourceId)
    sessionStore.setCurrentSession(session)
    messages.value = [] // Clear messages for new session
    selectDatasetDialogVisible.value = false // Close the dialog
    ElMessage.success('新对话创建成功')
  } catch (error) {
    console.error('创建新会话失败:', error)
    ElMessage.error('创建新会话失败')
  }
}

const switchSession = async (sessionId: string) => {
  await sessionStore.setCurrentSessionById(sessionId)
  messages.value = []
  ElMessage.success(`切换到会话 ${sessionId.slice(0, 8)}...`)
}

// --- Method to add quick prompts ---
const addSampleQuestion = (question: string) => {
  userInput.value = question
}

// --- Method to navigate to data management ---
const goToAddData = () => {
  router.push('/data-management')
}

// --- Existing Chat Logic Methods ---
const scrollToBottom = (): void => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 只提取“下一步建议”或“下一步行动建议”区域的建议
const extractSuggestions = (content: string): string[] => {
  // 兼容“**下一步建议**”或“**下一步行动建议**”后有冒号、空行，提取后续所有内容直到下一个空行或结尾
  const match = content.match(/\*\*(下一步建议|下一步行动建议)\*\*[:：]?\s*\n*([\s\S]*?)(?=\n{2,}|$)/)
  if (!match) return []
  // 只提取第一个有序列表（1. ...）开始的所有有序条目
  const lines = match[2].split('\n')
  const suggestions: string[] = []
  let inList = false
  for (const line of lines) {
    if (/^\d+\.\s+/.test(line)) {
      inList = true
      suggestions.push(line.replace(/^\d+\.\s+/, '').trim())
    } else if (inList && !line.trim()) {
      // 有序列表后遇到空行则停止
      break
    } else if (inList && !/^\d+\.\s+/.test(line)) {
      // 有序列表中遇到非有序项也停止
      break
    }
  }
  return suggestions
}

// 工具函数：去除markdown粗体、冒号和多余空格，只取建议标题部分
const stripSuggestion = (s: string) => {
  const clean = s.replace(/\*\*/g, '').trim()
  const idx = clean.indexOf('：')
  return idx !== -1 ? clean.slice(0, idx) : clean
}

const sendMessage = async (): Promise<void> => {
  if (!userInput.value.trim()) return
  if (!currentDataset.value) {
    ElMessage.warning('请先选择或上传一个数据集。')
    return
  }
  if (isProcessingChat.value) return

  isProcessingChat.value = true
  const userMessage = userInput.value.trim()
  const isFirstMessage = messages.value.length === 0 // 检查是否为第一条消息

  messages.value.push({
    type: 'user',
    content: userMessage,
    timestamp: new Date().toISOString()
  })
  userInput.value = ''
  scrollToBottom()
  try {
    // 创建一个初始的空AI回复消息
    const assistantMessage = reactive({
      type: 'assistant',
      content: [],
      timestamp: new Date().toISOString(),
      tool_calls: {},
      loading: true,
      suggestions: [],
    } as AssistantChatMessage & { loading?: boolean, suggestions?: string[] })
    messages.value.push(assistantMessage)

    const pushText = (content: string) => {
      if (!assistantMessage.content.length || assistantMessage.content[assistantMessage.content.length - 1].type !== 'text') {
        assistantMessage.content.push({ type: 'text', content })
        return content
      }
      const lastText = assistantMessage.content[assistantMessage.content.length - 1] as { content: string }
      lastText.content += content
      return lastText.content
    }

    // 使用流式API
    await sessionStore.sendStreamChatMessage(
      userMessage,
      (content) => {
        content = pushText(content)

        // 自动提取建议
        const suggestions = extractSuggestions(content)
        if (suggestions.length) {
          assistantMessage.suggestions = suggestions
        }

        nextTick(() => scrollToBottom())
      },
      (id, name, args) => {
        // 工具调用
        if (!assistantMessage.tool_calls) assistantMessage.tool_calls = {}
        assistantMessage.tool_calls[id] = {
          name,
          args,
          status: 'running'
        }
        assistantMessage.content.push({ type: 'tool_call', id })
        nextTick(() => scrollToBottom())
      },
      (id, result, artifact) => {
        // 工具结果
        // 更新工具调用状态
        const toolCall = assistantMessage.tool_calls?.[id] || undefined
        if (toolCall) {
          toolCall.status = 'success'
          toolCall.result = result
          toolCall.artifact = artifact || null
        }

        nextTick(() => scrollToBottom())
      },
      (id, error) => {
        // 工具错误
        // 更新工具调用状态
        const toolCall = assistantMessage.tool_calls?.[id] || undefined
        if (toolCall) {
          toolCall.status = 'error'
          toolCall.error = error
        }

        nextTick(() => scrollToBottom())
      },
      () => {
        // 完成处理
        console.log('对话完成')
        assistantMessage.loading = false

        // 如果是第一条消息，触发父组件重新加载会话列表（以获取更新的会话名称）
        if (isFirstMessage) {
          // 重新加载会话
          nextTick(() => {
            sessionStore.listSessions()
            scrollToBottom()
          })
        }
      },
      (error) => {
        // 错误处理
        console.error('对话处理错误:', error)
        ElMessage.error(`处理消息时出错: ${error}`)
        pushText(`\n\n处理出错: ${error}`)
        nextTick(() => scrollToBottom())
      }
    )

    assistantMessage.loading = false
  } catch (error) {
    console.error('发送消息失败:', error)

    // 添加错误消息
    messages.value.push({
      type: 'assistant',
      content: [{ type: 'text', content: '抱歉，处理您的请求时出现了错误。请稍后重试。' }],
      timestamp: new Date().toISOString()
    })

    await nextTick()
    scrollToBottom()
  } finally {
    isProcessingChat.value = false
  }
}

// --- Lifecycle Hooks ---
onMounted(async () => {
  await loadSessions()
  await dataSourceStore.listDataSources() // 加载数据源
  // if (!currentSessionId.value && appStore.sessions.length > 0) {
  //   appStore.setCurrentSession(appStore.sessions[0].id)
  // } else if (appStore.sessions.length === 0) {
  //   await createNewSession()
  // }
})
</script>

<template>
  <div class="chat-analysis-container">

    <!-- Session Sidebar -->
    <div :class="['session-sidebar', { 'is-closed': !isSidebarOpen }]">
      <div class="sidebar-header">
        <el-button class="new-chat-btn" @click="selectDatasetDialogVisible = true" :icon="Plus">
          新对话
        </el-button>
        <el-button @click="isSidebarOpen = false" :icon="DArrowLeft" text class="toggle-btn" />
      </div>
      <div class="session-list">
        <div v-for="session in sessions" :key="session.id"
          :class="['session-item', { active: session.id === currentSessionId }]" @click="switchSession(session.id)">
          <el-icon class="session-icon">
            <ChatDotRound />
          </el-icon>
          <span class="session-name">会话 {{ session.id.slice(0, 8) }}</span>
          <div class="session-actions">
            <el-button type="text" :icon="Edit" size="small" class="action-btn" />
            <el-button type="text" :icon="Delete" size="small" class="action-btn" />
          </div>
        </div>
      </div>
    </div>

    <!-- Chat Panel -->
    <div class="chat-panel">
      <div class="chat-panel-header">
        <el-button v-if="!isSidebarOpen" @click="isSidebarOpen = true" :icon="DArrowRight" text class="toggle-btn" />
        <span class="session-title" v-if="currentSessionId">
          会话: {{ currentSessionId.slice(0, 8) }}...
        </span>
      </div>      <div class="chat-messages" ref="messagesContainer">
        <div v-if="!messages.length" class="empty-state">
          <div class="empty-message">
            <p>选择一个数据集，开始您的数据分析对话</p>
          </div>
        </div>
        <div v-for="(message, index) in messages" :key="index">
          <AssistantMessage v-if="message.type === 'assistant'" :message="message" />
          <div v-else class="user-message-container">
            <div class="user-message">
              {{ message.content }}
            </div>
          </div>
          <!-- 建议按钮渲染 -->
          <div v-if="message.suggestions && message.suggestions.length" class="suggestion-buttons">
            <el-button v-for="(suggestion, idx) in message.suggestions" :key="idx" size="small"
              @click="addSampleQuestion(stripSuggestion(suggestion))" style="margin: 4px 4px 0 0;">
              {{ stripSuggestion(suggestion) }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="chat-input-wrapper">
          <el-input v-model="userInput" placeholder="输入你的问题..." @keyup.enter.native.prevent="sendMessage" resize="none"
            type="textarea" :autosize="{ minRows: 1, maxRows: 5 }" :disabled="isProcessingChat" />
          <el-button @click="sendMessage" :disabled="isProcessingChat || !userInput.trim()" type="primary"
            class="send-button">
            发送
          </el-button>
        </div>        <div class="quick-actions">
          <div class="dataset-indicator">
            <template v-if="currentDataset">
              <el-icon><DocumentCopy /></el-icon>
              当前数据集: <strong>{{ currentDataset.name || currentDataset.id.slice(0, 12) + '...' }}</strong>
              <el-link type="primary" @click="goToAddData" :underline="false">
                <el-icon><Edit /></el-icon>
                更换
              </el-link>
            </template>
            <template v-else>
              <el-icon><WarningFilled /></el-icon>
              <el-link type="warning" @click="goToAddData" :underline="false">
                请先选择一个数据集进行分析
              </el-link>
            </template>
          </div>
          <el-divider direction="vertical" style="margin: 0 8px;" />
          <div class="quick-prompt-tags">
            <el-tag class="action-tag" @click="addSampleQuestion('分析数据的基本统计信息')">
              <el-icon><DataAnalysis /></el-icon>
              基本统计
            </el-tag>
            <el-tag class="action-tag" @click="addSampleQuestion('绘制各列的相关性热力图')">
              <el-icon><PieChart /></el-icon>
              相关性分析
            </el-tag>
            <el-tag class="action-tag" @click="addSampleQuestion('检测并可视化异常值')">
              <el-icon><Search /></el-icon>
              异常检测
            </el-tag>
            <el-tag class="action-tag" @click="addSampleQuestion('生成数据质量报告')">
              <el-icon><Document /></el-icon>
              质量报告
            </el-tag>
          </div>
        </div>
      </div>
    </div>    <!-- Select Dataset Dialog -->
    <el-dialog v-model="selectDatasetDialogVisible" title="选择数据集以创建会话" width="600px">
      <el-empty v-if="!Object.keys(dataSourceStore.dataSources).length" description="暂无数据集，请先上传或选择一个数据集。">
        <el-button type="primary" @click="goToAddData">前往添加数据集</el-button>
      </el-empty>
      <div v-else class="dataset-list">
        <div 
          v-for="[sourceId, metadata] in Object.entries(dataSourceStore.dataSources)" 
          :key="sourceId"
          class="dataset-item"
          @click="createNewSession(sourceId)"
        >
          <div class="dataset-info">
            <el-icon><DocumentCopy /></el-icon>
            <div class="dataset-details">
              <div class="dataset-name">{{ metadata.name }}</div>
              <div class="dataset-description">{{ metadata.description || '暂无描述' }}</div>
            </div>
          </div>
          <el-button type="primary" size="small">选择</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="selectDatasetDialogVisible = false">取消</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<style lang="scss" scoped>
.chat-analysis-container {
  display: flex;
  height: calc(100vh - 80px);
  background-color: #ffffff;
}

// --- Sidebar Styles ---
.session-sidebar {
  width: 260px;
  flex-shrink: 0;
  background-color: #ffffff;
  color: #374151;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  border-right: 1px solid #e5e7eb;

  &.is-closed {
    width: 0;
  }
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  flex-shrink: 0;
  border-bottom: 1px solid #e5e7eb;
}

.new-chat-btn {
  flex-grow: 1;
  margin-right: 8px;
  background-color: transparent;
  border: 1px solid #d1d5db;
  color: #374151;
  justify-content: flex-start;
  border-radius: 8px;
  font-weight: 500;
  padding: 8px 12px;
  transition: all 0.2s ease;

  &:hover {
    background-color: #f3f4f6;
    border-color: #9ca3af;
  }

  &:focus {
    border-color: #10b981;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
  }
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


.session-list {
  flex-grow: 1;
  overflow-y: auto;
  padding: 8px 12px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;
    
    &:hover {
      background: #a8a8a8;
    }
  }
}

.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  color: #374151;
  font-weight: 500;

  .session-icon {
    margin-right: 12px;
    color: #6b7280;
    font-size: 16px;
  }

  .session-name {
    flex-grow: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 14px;
  }

  .session-actions {
    display: none;
    align-items: center;
    gap: 4px;

    .action-btn {
      color: #9ca3af;
      padding: 4px;
      border-radius: 4px;
      transition: all 0.2s ease;

      &:hover {
        color: #374151;
        background-color: #f3f4f6;
      }
    }
  }

  &:hover {
    background-color: #f9fafb;
    
    .session-icon {
      color: #374151;
    }

    .session-actions {
      display: flex;
    }
  }

  &.active {
    background-color: #f3f4f6;
    color: #10b981;
    
    .session-icon {
      color: #10b981;
    }
    
    &:hover {
      background-color: #f3f4f6;
    }
  }
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
  padding: 0 16px;
  height: 60px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
  background: #ffffff;

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

.chat-messages {
  flex-grow: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  background: #ffffff;
  
  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;
    
    &:hover {
      background: #a8a8a8;
    }
  }
}

.user-message-container {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.user-message {
  background: #f3f4f6;
  color: #1f2937;
  padding: 12px 16px;
  border-radius: 18px 18px 6px 18px;
  max-width: 70%;
  word-wrap: break-word;
  font-size: 14px;
  line-height: 1.5;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #6b7280;
  
  .empty-message {
    text-align: center;
    max-width: 400px;
    padding: 40px 20px;
    
    p {
      font-size: 16px;
      color: #6b7280;
      margin: 0;
      line-height: 1.6;
    }
  }
}

.chat-input-area {
  padding: 16px 24px 24px;
  background-color: #ffffff;
  border-top: 1px solid #e5e7eb;
}

.chat-input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background-color: #ffffff;
  border-radius: 12px;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  transition: all 0.2s ease;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);

  &:focus-within {
    border-color: #10b981;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
  }
}

.el-textarea {
  flex: 1;
  
  :deep(.el-textarea__inner) {
    box-shadow: none !important;
    background: transparent;
    border: none;
    padding: 0;
    font-size: 14px;
    line-height: 1.5;
    resize: none;
    
    &:focus {
      outline: none;
    }
    
    &::placeholder {
      color: #9ca3af;
    }
  }
}

.send-button {
  flex-shrink: 0;
  background: #10b981;
  border-color: #10b981;
  border-radius: 8px;
  padding: 8px 16px;
  font-weight: 500;
  transition: all 0.2s ease;
  
  &:hover {
    background: #059669;
    border-color: #059669;
    transform: translateY(-1px);
  }
  
  &:disabled {
    background: #d1d5db;
    border-color: #d1d5db;
    transform: none;
  }
}

.quick-actions {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  padding: 12px 16px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.dataset-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
  padding: 4px 8px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  
  .el-icon {
    font-size: 14px;
  }
  
  strong {
    color: #374151;
  }
  
  .el-link {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 8px;
    font-size: 12px;
    
    .el-icon {
      font-size: 12px;
    }
  }
}

.quick-prompt-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.action-tag {
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: #ffffff;
  color: #6b7280;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;

  .el-icon {
    font-size: 12px;
  }

  &:hover {
    background-color: #f3f4f6;
    color: #374151;
    border-color: #d1d5db;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }
}

.suggestion-buttons {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  
  .el-button {
    border-radius: 20px;
    font-size: 12px;
    padding: 4px 12px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    color: #6b7280;
    transition: all 0.2s ease;
    
    &:hover {
      background: #e5e7eb;
      color: #374151;
      border-color: #d1d5db;
      transform: translateY(-1px);
    }
  }
}

/* 数据集选择对话框样式 */
.dataset-list {
  max-height: 400px;
  overflow-y: auto;
  
  .dataset-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    margin-bottom: 8px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    
    &:hover {
      background-color: #f9fafb;
      border-color: #10b981;
    }
    
    .dataset-info {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
      
      .el-icon {
        color: #6b7280;
        font-size: 18px;
      }
      
      .dataset-details {
        .dataset-name {
          font-weight: 500;
          color: #1f2937;
          margin-bottom: 4px;
        }
        
        .dataset-description {
          font-size: 12px;
          color: #6b7280;
        }
      }
    }
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

.tool-artifact {
  margin-top: 10px;
}

.image-artifact {
  text-align: center;
}

.image-caption {
  margin-top: 5px;
  font-style: italic;
  color: #6b7280;
}
</style>
