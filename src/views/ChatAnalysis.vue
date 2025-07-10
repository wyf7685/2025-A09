<script setup lang="ts">
import { useAppStore } from '@/stores/app';
import type { AssistantChatMessage, ChatEntry, ChatMessage } from '@/types';
import { ElMessage } from 'element-plus';
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import AssistantMessage from '@/components/AssistantMessage.vue';
import { useSessionStore } from '@/stores/session';
import { useDataSourceStore } from '@/stores/datasource';

// const appStore = useAppStore()
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();

// 响应式数据
const inputMessage = ref<string>('')
const messages = ref<ChatMessage[]>([])
const messagesContainer = ref<HTMLElement | null>(null)
const loading = ref<boolean>(false);

// 计算属性
const currentDataset = computed(() =>
  sessionStore.currentSession
    ? dataSourceStore.dataSources[sessionStore.currentSession.dataset_id]
    : null
);

const formatTime = (timestamp: string | undefined): string => {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleTimeString('zh-CN')
}

const addSampleQuestion = (question: string): void => {
  inputMessage.value = question
}

const sendMessage = async (): Promise<void> => {
  if (!inputMessage.value.trim()) {
    ElMessage.warning('请输入消息内容')
    return
  }

  if (!currentDataset.value) {
    ElMessage.warning('请先上传数据集')
    return
  }

  const userMessage = inputMessage.value.trim()

  // 添加用户消息
  messages.value.push({
    type: 'user',
    content: userMessage,
    timestamp: new Date().toISOString()
  })

  // 清空输入
  inputMessage.value = ''

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  try {
    // 创建一个初始的空AI回复消息
    const assistantMessage = reactive({
      type: 'assistant',
      content: [],
      timestamp: new Date().toISOString(),
      tool_calls: {},
      loading: true,
    } as AssistantChatMessage & { loading?: boolean })
    messages.value.push(assistantMessage)

    // 使用流式API
    await sessionStore.sendStreamChatMessage(
      userMessage,
      (content) => {
        // LLM 输出
        assistantMessage.content.push({ type: 'text', content })
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
      },
      (error) => {
        // 错误处理
        console.error('对话处理错误:', error)
        assistantMessage.loading = false
        assistantMessage.content.push({
          type: 'text',
          content: `\n\n处理出错: ${error}`
        })
        assistantMessage.loading = true
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
  }
}

const clearChat = (): void => {
  messages.value = []
  ElMessage.success('对话已清空')
}

const scrollToBottom = (): void => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const loadChatHistory = (): void => {
  // 从 store 中加载聊天历史
  const history: ChatEntry[] = sessionStore.chatHistory
  messages.value = history.map(entry => [entry.user_message, entry.assistant_response]).flat()

  nextTick(() => {
    scrollToBottom()
  })
}

// 监听数据集变化
watch(currentDataset, (newDataset) => {
  if (newDataset && messages.value.length === 0) {
    // 添加欢迎消息
    const welcome = `您好！我是您的AI数据分析助手。当前已加载数据集 "${newDataset.id}"，包含 ${newDataset.row_count || 0} 行和 ${newDataset.column_count || 0} 列数据。\n\n您可以问我：\n- 数据的基本统计信息\n- 绘制各种图表\n- 进行相关性分析\n- 检测异常值\n- 数据聚类分析\n\n请告诉我您想了解什么！`

    messages.value.push({
      type: 'assistant',
      content: [{ type: 'text', content: welcome }],
      timestamp: new Date().toISOString()
    })

    nextTick(() => {
      scrollToBottom()
    })
  }
})

// 生命周期
onMounted(() => {
  loadChatHistory()
})
</script>

<template>
  <div class="chat-analysis">
    <div class="chat-container">
      <!-- 聊天消息区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <div v-if="!sessionStore.currentSession" class="empty-state">
          <el-empty>
            <template #image>
              <el-icon style="font-size: 64px; color: #ddd;">
                <DataBoard />
              </el-icon>
            </template>
            <template #description>
              <p>暂无会话，请先从数据源创建会话</p>
              <br>
              <el-button type="primary" @click="$router.push('/data-sources')">
                前往数据源
              </el-button>
            </template>
          </el-empty>
        </div>

        <div v-else-if="messages.length === 0" class="empty-state">
          <el-empty description="开始您的数据分析对话吧！">
            <template #image>
              <el-icon style="font-size: 64px; color: #ddd;">
                <ChatDotRound />
              </el-icon>
            </template>
          </el-empty>
        </div>

        <template v-else>
          <div v-for="(message, index) in messages" :key="index" :class="['message-item', message.type]">
            <div class="message-content">
              <div v-if="message.type === 'user'" class="user-message">
                {{ message.content }}
              </div>
              <AssistantMessage v-else :message="message" class="assistant-message"></AssistantMessage>
            </div>
            <div class="message-time">
              {{ formatTime(message.timestamp) }}
            </div>
          </div>
        </template>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input">
        <el-input v-model="inputMessage" type="textarea" :rows="3"
          placeholder="输入您想了解的数据分析问题，例如：分析数据的基本统计信息、查找异常值、绘制相关性热力图等..." @keydown.ctrl.enter="sendMessage"
          :disabled="!currentDataset || loading" />

        <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <el-tag v-if="currentDataset" type="success" size="small">
              当前数据集: {{ currentDataset.name }}
            </el-tag>
            <el-tag v-else type="warning" size="small">
              未选择数据集
            </el-tag>
            <el-button size="small" @click="addSampleQuestion('分析数据的基本统计信息')">
              基本统计
            </el-button>
            <el-button size="small" @click="addSampleQuestion('绘制各列的相关性热力图')">
              相关性分析
            </el-button>
            <el-button size="small" @click="addSampleQuestion('检测并可视化异常值')">
              异常检测
            </el-button>
            <el-button size="small" @click="addSampleQuestion('对数据进行聚类分析')">
              聚类分析
            </el-button>
          </div>

          <div>
            <el-button @click="clearChat" size="small">清空对话</el-button>
            <el-button type="primary" @click="sendMessage" :loading="loading"
              :disabled="!inputMessage.trim() || !currentDataset">
              <el-icon>
                <Promotion />
              </el-icon>
              发送 (Ctrl+Enter)
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-analysis {
  height: calc(100vh - 90px);
  display: flex;
  flex-direction: column;
}

.chat-container {
  height: 100%;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f8f9fa;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-item {
  margin-bottom: 20px;

  &.user {
    text-align: right;

    .message-content {
      background: #409EFF;
      color: white;
      border-radius: 18px 18px 6px 18px;
    }
  }

  &.assistant {
    text-align: left;

    .message-content {
      background: white;
      color: #333;
      border-radius: 18px 18px 18px 6px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
  }
}

.message-content {
  display: inline-block;
  max-width: 75%;
  padding: 12px 16px;
  word-wrap: break-word;
}

.message-time {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.assistant-text {
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 工具调用样式 */
.tool-calls {
  margin-top: 15px;
  border-top: 1px solid #eee;
  padding-top: 10px;
}

.tool-call {
  background: #f9f9f9;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
  border-left: 3px solid #909399;

  &.running {
    border-left-color: #E6A23C;
  }

  &.success {
    border-left-color: #67C23A;
  }

  &.error {
    border-left-color: #F56C6C;
  }
}

.tool-header {
  display: flex;
  align-items: center;
  font-weight: bold;
  margin-bottom: 5px;

  .el-icon {
    margin-right: 5px;
  }
}

.tool-args {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 8px;

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
  }
}

.tool-result {
  background: #f0f9eb;
  padding: 8px;
  border-radius: 4px;

  .result-label {
    font-weight: bold;
    color: #67C23A;
    margin-bottom: 5px;
  }

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
  }
}

.tool-error {
  background: #fef0f0;
  padding: 8px;
  border-radius: 4px;

  .error-label {
    font-weight: bold;
    color: #F56C6C;
    margin-bottom: 5px;
  }

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
    color: #F56C6C;
  }
}

.charts-container {
  margin-top: 12px;
}

.rotating {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
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
</style>
