<script setup lang="ts">
import { ref, onMounted, computed, nextTick, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, ChatDotRound, Delete, Edit, DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import AssistantMessage from '@/components/AssistantMessage.vue'
import type { ChatMessage, AssistantChatMessage } from '@/types'
import { ElMessage } from 'element-plus'

const router = useRouter()
const appStore = useAppStore()

// --- State for new UI ---
const isSidebarOpen = ref(true)

// --- Existing Chat Logic State ---
const userInput = ref('')
const messages = ref<ChatMessage[]>([])
const messagesContainer = ref<HTMLElement | null>(null)

// --- Computed Properties ---
const sessions = computed(() => appStore.sessions)
const currentSessionId = computed(() => appStore.currentSessionId)
const isLoading = computed(() => appStore.loading)
const currentDataset = computed(() => appStore.currentDataset)


// --- Methods for new UI ---
const loadSessions = async () => {
  try {
    await appStore.getSessions()
  } catch (error) {
    console.error('加载会话失败:', error)
  }
}

const createNewSession = async () => {
  try {
    await appStore.createNewSessionAndSetCurrent()
    messages.value = [] // Clear messages for new session
  } catch (error) {
    console.error('创建新会话失败:', error)
    ElMessage.error('创建新会话失败')
  }
}

const switchSession = (sessionId: string) => {
  appStore.setCurrentSession(sessionId)
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

const sendMessage = async (): Promise<void> => {
  if (!userInput.value.trim()) return
  if (!currentDataset.value) {
    ElMessage.warning('请先选择或上传一个数据集。')
    return
  }
  if (isLoading.value) return

  const userMessageContent = userInput.value.trim()
  messages.value.push({
    type: 'user',
    content: userMessageContent,
    timestamp: new Date().toISOString()
  })
  userInput.value = ''
  scrollToBottom()

  const assistantMessage = reactive<AssistantChatMessage>({
    type: 'assistant',
    content: [],
    timestamp: new Date().toISOString(),
    tool_calls: {},
  })
  messages.value.push(assistantMessage)
  scrollToBottom()

  await appStore.sendStreamChatMessage(
    userMessageContent,
    // onMessage
    (content) => {
      assistantMessage.content.push({ type: 'text', content })
      scrollToBottom()
    },
    // onToolCall
    (id, name, args) => {
      if (!assistantMessage.tool_calls) assistantMessage.tool_calls = {}
      assistantMessage.tool_calls[id] = { name, args, status: 'running' }
      assistantMessage.content.push({ type: 'tool_call', id })
      scrollToBottom()
    },
    // onToolResult
    (id, result, artifact) => {
      const toolCall = assistantMessage.tool_calls?.[id]
      if (toolCall) {
        toolCall.status = 'success'
        toolCall.result = result
        toolCall.artifact = artifact || null
      }
      scrollToBottom()
    },
    // onToolError
    (id, error) => {
       const toolCall = assistantMessage.tool_calls?.[id]
       if (toolCall) {
         toolCall.status = 'error'
         toolCall.error = error
       }
       scrollToBottom()
    },
    // onDone
    () => {
      console.log("Stream finished.")
      scrollToBottom()
    },
    // onError
    (error) => {
      console.error('Stream error:', error)
      ElMessage.error(`请求出错: ${error}`)
      assistantMessage.content.push({ type: 'text', content: `\n\n处理出错: ${error}` })
      scrollToBottom()
    }
  )
}


// --- Lifecycle Hooks ---
onMounted(async () => {
  await loadSessions()
  if (!currentSessionId.value && appStore.sessions.length > 0) {
    appStore.setCurrentSession(appStore.sessions[0].id)
  } else if (appStore.sessions.length === 0) {
    await createNewSession()
  }
})

</script>

<template>
  <div class="chat-analysis-container">
    <!-- Session Sidebar -->
    <div :class="['session-sidebar', { 'is-closed': !isSidebarOpen }]">
      <div class="sidebar-header">
        <el-button class="new-chat-btn" @click="createNewSession" :icon="Plus">
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
         </div>
       </div>

      <div class="chat-input-area">
        <div class="chat-input-wrapper">
          <el-input v-model="userInput" placeholder="输入你的问题..." @keyup.enter.native.prevent="sendMessage"
            resize="none" type="textarea" :autosize="{ minRows: 1, maxRows: 5 }" :disabled="isLoading" />
          <el-button @click="sendMessage" :disabled="isLoading || !userInput.trim()" type="primary" class="send-button">
            发送
          </el-button>
        </div>
        <div class="quick-actions">
           <div class="dataset-indicator">
            <template v-if="currentDataset">
              当前数据集: <strong>{{ currentDataset.id.slice(0, 12) }}...</strong> ( <el-link type="primary" @click="goToAddData" :underline="false">更换</el-link> )
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
  min-width: 0; /* Important for flex-grow to work correctly */
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

</style>
