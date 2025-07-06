<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { marked } from 'marked';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useAppStore } from '@/stores/app';
import type { ChatMessage, ChatEntry } from '@/types';

const appStore = useAppStore()

// 响应式数据
const inputMessage = ref<string>('')
const messages = ref<ChatMessage[]>([])
const messagesContainer = ref<HTMLElement | null>(null)

// 计算属性
const currentDataset = computed(() => appStore.currentDataset)

// 方法
const formatMessage = async (content: string | undefined): Promise<string> => {
  // 使用 marked 将 Markdown 转换为 HTML
  return await marked(content || '')
}

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
    // 发送消息到后端
    const response = await appStore.sendChatMessage(
      userMessage,
      appStore.currentSessionId,
      currentDataset.value.id
    )

    // 添加AI回复
    const assistantMessage: ChatMessage = {
      type: 'assistant',
      content: response.chat_entry.content || '抱歉，我无法处理您的请求。',
      timestamp: response.chat_entry?.timestamp || new Date().toISOString(),
      execution_results: response.chat_entry?.execution_results,
      charts: []
    }

    // 处理图表数据
    if (response.chat_entry?.execution_results) {
      assistantMessage.charts = response.chat_entry.execution_results
        .map(result => result.figure)
        .filter(figure => figure !== undefined)
    }

    messages.value.push(assistantMessage)

    // 滚动到底部
    await nextTick()
    scrollToBottom()

  } catch (error) {
    console.error('发送消息失败:', error)

    // 添加错误消息
    messages.value.push({
      type: 'assistant',
      content: '抱歉，处理您的请求时出现了错误。请稍后重试。',
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
  const history: ChatEntry[] = appStore.chatHistory
  messages.value = history.map(entry => [
    {
      type: 'user' as const,
      content: entry.user_message!,
      timestamp: entry.timestamp
    },
    {
      type: 'assistant' as const,
      content: entry.assistant_response!,
      timestamp: entry.timestamp,
      execution_results: entry.execution_results,
      charts: entry.execution_results?.map(r => r.figure).filter(figure => figure !== undefined) || []
    }
  ]).flat()

  nextTick(() => {
    scrollToBottom()
  })
}

// 监听数据集变化
watch(currentDataset, (newDataset) => {
  if (newDataset && messages.value.length === 0) {
    // 添加欢迎消息
    messages.value.push({
      type: 'assistant',
      content: `您好！我是您的AI数据分析助手。当前已加载数据集 "${newDataset.id}"，包含 ${newDataset.overview?.shape?.[0] || 0} 行和 ${newDataset.overview?.shape?.[1] || 0} 列数据。\n\n您可以问我：\n- 数据的基本统计信息\n- 绘制各种图表\n- 进行相关性分析\n- 检测异常值\n- 数据聚类分析\n\n请告诉我您想了解什么！`,
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
        <div v-if="messages.length === 0" class="empty-state">
          <el-empty description="开始您的数据分析对话吧！">
            <template #image>
              <el-icon style="font-size: 64px; color: #ddd;">
                <ChatDotRound />
              </el-icon>
            </template>
          </el-empty>
        </div>

        <div v-for="(message, index) in messages" :key="index" :class="['message-item', message.type]">
          <div class="message-content">
            <div v-if="message.type === 'user'" class="user-message">
              {{ message.content }}
            </div>
            <div v-else class="assistant-message">
              <!-- AI回复内容 -->
              <div class="message-text" v-html="formatMessage(message.content)"></div>

              <!-- 如果有图表，显示图表 -->
              <div v-if="message.charts && message.charts.length > 0" class="charts-container">
                <div v-for="(chart, chartIndex) in message.charts" :key="chartIndex" class="chart-item">
                  <img :src="`data:image/png;base64,${chart}`" alt="分析图表" />
                </div>
              </div>

              <!-- 执行结果 -->
              <div v-if="message.execution_results" class="execution-results">
                <el-collapse>
                  <el-collapse-item v-for="(result, resultIndex) in message.execution_results" :key="resultIndex"
                    :title="`执行结果 ${resultIndex + 1}: ${result.query}`">
                    <div class="result-content">
                      <div v-if="result.output" class="result-output">
                        <h5>输出:</h5>
                        <pre>{{ result.output }}</pre>
                      </div>
                      <div v-if="result.figure" class="result-figure">
                        <h5>图表:</h5>
                        <img :src="`data:image/png;base64,${result.figure}`" alt="执行结果图表" />
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>
          <div class="message-time">
            {{ formatTime(message.timestamp) }}
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-if="appStore.loading" class="message-item assistant">
          <div class="message-content">
            <el-icon class="rotating">
              <Loading />
            </el-icon>
            <span style="margin-left: 8px;">AI 正在分析中...</span>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input">
        <div style="margin-bottom: 12px;">
          <el-tag v-if="currentDataset" type="success" size="small">
            当前数据集: {{ currentDataset.id }}
          </el-tag>
          <el-tag v-else type="warning" size="small">
            未选择数据集
          </el-tag>
        </div>

        <el-input v-model="inputMessage" type="textarea" :rows="3"
          placeholder="输入您想了解的数据分析问题，例如：分析数据的基本统计信息、查找异常值、绘制相关性热力图等..." @keydown.ctrl.enter="sendMessage"
          :disabled="!currentDataset || appStore.loading" />

        <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
          <div>
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
            <el-button type="primary" @click="sendMessage" :loading="appStore.loading"
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
  height: calc(100vh - 140px);
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

.message-text {
  line-height: 1.6;
}

.charts-container {
  margin-top: 12px;
}

.chart-item {
  margin-bottom: 8px;
}

.chart-item img {
  max-width: 100%;
  border-radius: 4px;
}

.execution-results {
  margin-top: 12px;
}

.result-content {
  padding: 8px 0;
}

.result-output pre {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}

.result-figure img {
  max-width: 100%;
  border-radius: 4px;
}

.chat-input {
  padding: 20px;
  background: white;
  border-top: 1px solid #e4e7ed;
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
</style>
