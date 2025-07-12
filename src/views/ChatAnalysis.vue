<script setup lang="ts">
import AssistantMessage from '@/components/AssistantMessage.vue';
import { useDataSourceStore } from '@/stores/datasource';
import { useSessionStore } from '@/stores/session';
import type { AssistantChatMessage, ChatMessage } from '@/types';
import { ChatDotRound, DArrowLeft, DArrowRight, Delete, Edit, Plus } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, nextTick, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

type ChatMessageWithSuggestions = ChatMessage & { loading?: boolean, suggestions?: string[] }

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
  const match = content.match(/\*?\*?(下一步建议|下一步行动建议)\*?\*?[:：]?\s*\n*([\s\S]*?)(?=\n{2,}|$)/)
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
      </div>

      <div class="chat-messages" ref="messagesContainer">
        <div v-if="!messages.length" class="empty-state">
          <el-empty description="开始您的数据分析对话吧！" />
        </div>
        <div v-for="(message, index) in messages" :key="index">
          <AssistantMessage v-if="message.type === 'assistant'" :message="message" />
          <div v-else class="user-message-container">
            <div class="user-message">
              {{ message.content }}
            </div>
          </div>
          <div v-if="message.type === 'assistant' && message.loading">
            <el-icon>
              <Loading class="rotating" />
            </el-icon>
            正在处理...
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
        </div>
        <div class="quick-actions">
          <div class="dataset-indicator">
            <template v-if="currentDataset">
              当前数据集: <strong>{{ currentDataset.id.slice(0, 12) }}...</strong>
            </template>
            <template v-else>
              <el-link type="warning" @click="goToAddData" :underline="false">请先选择一个数据集进行分析</el-link>
            </template>
          </div>
          <el-tag class="action-tag" @click="addSampleQuestion('分析数据的基本统计信息')">基本统计</el-tag>
          <el-tag class="action-tag" @click="addSampleQuestion('绘制各列的相关性热力图')">相关性热力图</el-tag>
          <el-tag class="action-tag" @click="addSampleQuestion('检测并可视化异常值')">异常值检测</el-tag>
        </div>
      </div>
    </div>

    <!-- Select Dataset Dialog -->
    <el-dialog v-model="selectDatasetDialogVisible" title="选择数据集以创建会话" width="600px">
      <el-empty v-if="!dataSourceStore.dataSources.length">
        <template #description>暂无数据集，请先上传或选择一个数据集。
          <el-button type="primary" @click="goToAddData">前往添加数据集</el-button>
        </template>
      </el-empty>
      <el-list v-else>
        <el-list-item v-for="[sourceId, metadata] in Object.entries(dataSourceStore.dataSources)" :key="sourceId"
          @click="createNewSession(sourceId)">
          {{ metadata.name }}
        </el-list-item>
      </el-list>
      <template #footer>
        <el-button @click="selectDatasetDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<style lang="scss" scoped>
.chat-analysis-container {
  display: flex;
  height: calc(100vh - 80px);
  background-color: #f7f7f8;
}

// --- Sidebar Styles ---
.session-sidebar {
  width: 260px;
  flex-shrink: 0;
  background-color: #202123;
  color: white;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;

  &.is-closed {
    width: 0;
  }
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px;
  flex-shrink: 0;
}

.new-chat-btn {
  flex-grow: 1;
  margin-right: 8px;
  background-color: transparent;
  border: 1px solid #4a4a4f;
  color: white;
  justify-content: flex-start;

  &:hover {
    background-color: #2a2b2e;
  }
}

.toggle-btn {
  color: #a9a9a9;

  &:hover {
    color: white;
    background-color: #2a2b2e;
  }
}


.session-list {
  flex-grow: 1;
  overflow-y: auto;
  padding: 0 8px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: #43464a;
    border-radius: 3px;
  }
}

.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  white-space: nowrap;


  .session-icon {
    margin-right: 12px;
  }

  .session-name {
    flex-grow: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-actions {
    display: none;
    align-items: center;

    .action-btn {
      color: #b0b0b5;
      padding: 4px;

      &:hover {
        color: white;
      }
    }
  }

  &:hover {
    background-color: #2a2b2e;

    .session-actions {
      display: flex;
    }
  }

  &.active {
    background-color: #343541;
  }
}


// --- Chat Panel Styles ---
.chat-panel {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  /* Important for flex-grow to work correctly */
  height: 100%;
  position: relative;
  background: white;
}

.chat-panel-header {
  display: flex;
  align-items: center;
  padding: 0 8px;
  height: 49px; // Match sidebar header height
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;

  .session-title {
    font-weight: 500;
    margin-left: 8px;
  }
}

.chat-messages {
  flex-grow: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.user-message-container {
  display: flex;
  justify-content: flex-end;
}

.user-message {
  background: #3b82f6;
  color: white;
  padding: 10px 16px;
  border-radius: 18px 18px 6px 18px;
  max-width: 75%;
  word-wrap: break-word;
}


.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.chat-input-area {
  padding: 16px 24px;
  background-color: #ffffff;
  border-top: 1px solid #e5e7eb;
}

.chat-input-wrapper {
  display: flex;
  gap: 12px;
  align-items: center;
  background-color: #f4f4f5;
  border-radius: 12px;
  padding: 8px;
  border: 1px solid #e5e7eb;
  transition: box-shadow 0.2s;

  &:focus-within {
    border-color: #c0c4cc;
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
  }
}

.el-textarea {
  :deep(textarea) {
    box-shadow: none !important;
    background: transparent;
    border: none;
    padding-right: 10px;
  }
}

.send-button {
  flex-shrink: 0;
}

.quick-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.dataset-indicator {
  font-size: 12px;
  color: #606266;
  margin-right: 8px;
}

.action-tag {
  cursor: pointer;
  transition: all 0.2s;
  background-color: #f0f2f5;
  color: #606266;
  border-color: #e5e7eb;

  &:hover {
    background-color: #e4e7ed;
    color: #303133;
    border-color: #dcdfe6;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .message-content {
    max-width: 85%;
  }

  .chat-input {
    padding: 16px;
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
  color: #666;
}

.suggestion-buttons {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rotating {
  animation: rotating 2s linear infinite;
}
</style>
