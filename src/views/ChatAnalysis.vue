<script setup lang="ts">
import AssistantMessage from '@/components/AssistantMessage.vue';
import FlowPanel from '@/components/FlowPanel.vue';
import { useDataSourceStore } from '@/stores/datasource';
import { useSessionStore } from '@/stores/session';
import type { AssistantChatMessage, AssistantChatMessageContent, AssistantChatMessageText, ChatMessage } from '@/types';
import { turncateString } from '@/utils/tools';
import { ChatDotRound, DArrowLeft, DArrowRight, DataAnalysis, Delete, Document, DocumentCopy, Edit, Monitor, PieChart, Plus, Search, WarningFilled } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
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
const isFlowPanelOpen = ref<boolean>(true) // 控制流程图面板的显示/隐藏
const isDeletingSession = ref<boolean>(false) // 防止重复删除操作
const flowPanelRef = ref<InstanceType<typeof FlowPanel>>()

const sessions = computed(() => sessionStore.sessions)
const currentSessionId = computed(() => sessionStore.currentSession?.id)
const currentDataset = computed(() =>
  sessionStore.currentSession
    ? dataSourceStore.dataSources[sessionStore.currentSession.dataset_id]
    : null
);

// 会话编辑相关
const editSessionDialogVisible = ref(false)
const editingSessionId = ref('')
const editingSessionName = ref('')

const openEditSessionDialog = (sessionId: string, sessionName: string) => {
  editingSessionId.value = sessionId
  editingSessionName.value = sessionName
  editSessionDialogVisible.value = true
}

const saveSessionEdit = async () => {
  if (!editingSessionId.value || !editingSessionName.value.trim()) {
    ElMessage.warning('会话名称不能为空')
    return
  }

  try {
    await sessionStore.updateSessionName(editingSessionId.value, editingSessionName.value.trim())
    ElMessage.success('会话名称更新成功')
    editSessionDialogVisible.value = false
  } catch (error) {
    console.error('更新会话名称失败:', error)
    ElMessage.error('更新会话名称失败')
  }
}

// 修改confirmDeleteSession函数
const confirmDeleteSession = async (sessionId: string, sessionName: string) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除会话 "${sessionName}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    try {
      await sessionStore.deleteSession(sessionId)
      ElMessage.success('会话删除成功')

      // 如果删除的是当前会话，清空消息列表
      if (sessionId === currentSessionId.value) {
        messages.value = []
      }

      // 如果还有其他会话，自动切换到第一个
      if (sessions.value.length > 0) {
        await switchSession(sessions.value[0].id)
      }
    } catch (error) {
      console.error('删除会话失败:', error)
      ElMessage.error('删除会话失败，请稍后重试')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除会话对话框错误:', error)
    }
  }
}

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
    await refreshChatHistory()
    selectDatasetDialogVisible.value = false // Close the dialog
    ElMessage.success('新对话创建成功')
  } catch (error) {
    console.error('创建新会话失败:', error)
    ElMessage.error('创建新会话失败')
  }
}

const mergeTextPart = (parts: AssistantChatMessageContent[]): AssistantChatMessageContent[] => {
  const merged: AssistantChatMessageContent[] = [];
  for (const part of parts) {
    if (part.type !== 'text' || !merged.length || merged[merged.length - 1].type !== 'text') {
      merged.push(part);
    } else {
      const lastText = merged[merged.length - 1] as AssistantChatMessageText;
      lastText.content += part.content;
    }
  }
  return merged;
}

const refreshChatHistory = async () => {
  if (!currentSessionId.value) return
  const session = await sessionStore.getSession(currentSessionId.value)
  messages.value = session.chat_history.map((entry) => {
    const assistantMessage = {
      ...entry.assistant_response,
      content: mergeTextPart(entry.assistant_response.content),
    }

    // 重新提取建议按钮（页面刷新后恢复建议）
    const mergedContent = assistantMessage.content.map(c => c.type === 'text' ? c.content : '').join('')
    const suggestions = extractSuggestions(mergedContent)
    if (suggestions.length > 0) {
      (assistantMessage as any).suggestions = suggestions
    }

    return [entry.user_message, assistantMessage]
  }).flat() || []
  // 等 AssistantMessage 加载再滚动到底部
  nextTick(scrollToBottom)
}

const switchSession = async (sessionId: string) => {
  await sessionStore.setCurrentSessionById(sessionId)
  const session = sessions.value.find(s => s.id === sessionId)
  await refreshChatHistory()
  ElMessage.success(`切换到会话: ${session?.name || sessionId.slice(0, 8)}...`)
}

// 删除会话
const deleteSession = async (sessionId: string, event: Event) => {
  // 阻止事件冒泡，避免触发会话切换
  event.stopPropagation()

  // 防止重复操作
  if (isDeletingSession.value) return

  const session = sessions.value.find(s => s.id === sessionId)
  const sessionName = session?.name || sessionId.slice(0, 8) + '...'

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
    )

    isDeletingSession.value = true

    await sessionStore.deleteSession(sessionId)

    // 如果删除的是当前会话
    if (sessionId === currentSessionId.value) {
      messages.value = []
      flowPanelRef.value?.clearFlowSteps()

      // 如果还有其他会话，切换到第一个会话
      if (sessions.value.length > 0) {
        await switchSession(sessions.value[0].id)
      }
    }

    ElMessage.success(`会话 "${sessionName}" 已删除`)

    // 如果没有会话了，提示用户创建新会话
    if (sessions.value.length === 0) {
      ElMessage.info('所有会话已删除，请创建新会话开始分析')
    }

  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除会话失败:', error)
      ElMessage.error('删除会话失败')
    }
  } finally {
    isDeletingSession.value = false
  }
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

  // 如果是第一条消息，立即更新会话名称
  if (isFirstMessage && currentSessionId.value) {
    const sessionName = userMessage.length > 30 ? userMessage.substring(0, 30) + '...' : userMessage
    sessionStore.updateSessionName(currentSessionId.value, sessionName)
  }

  // 智能路线选择
  const selectedRouteForThisMessage = flowPanelRef.value?.autoSelectRoute(userMessage)

  // 更新固定路线步骤状态
  // 第一步：用户输入
  flowPanelRef.value?.logRouteStatus('开始处理用户输入')
  flowPanelRef.value?.updateRouteStep(0, 'completed')

  // 第二步：AI分析处理
  flowPanelRef.value?.updateRouteStep(1, 'active')

  // 设置超时保护，防止流程图永远卡在AI分析阶段
  const timeoutId = setTimeout(() => {
    console.warn('AI分析处理超时，强制完成流程图步骤')
    if (selectedRouteForThisMessage === 'route1') {
      flowPanelRef.value?.updateRouteStep(1, 'completed')
      flowPanelRef.value?.updateRouteStep(2, 'completed')
    } else {
      flowPanelRef.value?.updateRouteStep(1, 'completed')
      flowPanelRef.value?.updateRouteStep(2, 'completed')
      flowPanelRef.value?.updateRouteStep(4, 'completed')
    }
    flowPanelRef.value?.logRouteStatus('超时保护：强制完成流程')
  }, 30000) // 30秒超时

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

        // 如果AI开始输出内容，说明分析阶段基本完成
        if (content.length > 20) {
          if (selectedRouteForThisMessage === 'route1') {
            // 路线1：渐进式推进流程
            if (content.length > 50 && flowPanelRef.value?.route1Steps[1]?.status === 'active') {
              console.log('路线1：AI分析达到50字符，标记为完成')
              flowPanelRef.value?.updateRouteStep(1, 'completed') // AI分析处理完成
              flowPanelRef.value?.updateRouteStep(2, 'active')    // 开始生成报告
            }
            if (content.length > 200 && flowPanelRef.value?.route1Steps[2]?.status === 'active') {
              console.log('路线1：内容达到200字符，报告生成完成')
              flowPanelRef.value?.updateRouteStep(2, 'completed') // 生成报告完成
            }
          } else if (selectedRouteForThisMessage === 'route2') {
            // 路线2：如果还没有工具调用，可能是纯文本回复
            if (content.length > 50 && (!assistantMessage.tool_calls || Object.keys(assistantMessage.tool_calls).length === 0)) {
              console.log('路线2：纯文本回复，完成相应步骤')
              flowPanelRef.value?.updateRouteStep(1, 'completed') // AI分析处理完成
              flowPanelRef.value?.updateRouteStep(2, 'completed') // 判断执行工具完成（决定不需要工具）
            }
          }
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

        // 更新路线步骤：工具调用开始
        if (selectedRouteForThisMessage === 'route2') {
          flowPanelRef.value?.updateRouteStep(1, 'completed') // AI分析处理完成
          flowPanelRef.value?.updateRouteStep(2, 'completed') // 判断执行工具完成
          flowPanelRef.value?.updateRouteStep(3, 'active')    // 调用执行工具开始
        }

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

        // 工具调用完成，更新路线步骤
        if (selectedRouteForThisMessage === 'route2') {
          flowPanelRef.value?.updateRouteStep(3, 'completed') // 调用执行工具完成
          flowPanelRef.value?.updateRouteStep(4, 'active')    // 是否进行循环

          // 自动完成循环判断步骤（默认不循环）
          setTimeout(() => {
            flowPanelRef.value?.updateRouteStep(4, 'completed') // 完成循环判断
          }, 1000)
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
        console.log('selectedRouteForThisMessage:', selectedRouteForThisMessage)
        console.log('assistantMessage.tool_calls:', assistantMessage.tool_calls)

        // 清除超时保护
        clearTimeout(timeoutId)

        assistantMessage.loading = false
        flowPanelRef.value?.logRouteStatus('对话处理完成')

        // 根据路线和当前状态更新步骤
        if (selectedRouteForThisMessage === 'route1') {
          console.log('执行路线1完成逻辑')
          // 路线1：如果AI分析还在进行中，先完成它，然后完成生成报告
          flowPanelRef.value?.updateRouteStep(1, 'completed') // AI分析处理完成
          flowPanelRef.value?.updateRouteStep(2, 'completed') // 生成报告完成
        } else if (selectedRouteForThisMessage === 'route2') {
          console.log('执行路线2完成逻辑')
          // 路线2：检查当前状态并完成剩余步骤
          if (!assistantMessage.tool_calls || Object.keys(assistantMessage.tool_calls).length === 0) {
            console.log('路线2：没有工具调用')
            // 没有工具调用的情况
            flowPanelRef.value?.updateRouteStep(1, 'completed') // AI分析处理完成
            flowPanelRef.value?.updateRouteStep(2, 'completed') // 判断执行工具完成（决定不需要工具）
            flowPanelRef.value?.updateRouteStep(4, 'completed') // 直接完成，不进行循环
          } else {
            console.log('路线2：有工具调用')
            // 有工具调用的情况，确保最后一步完成
            flowPanelRef.value?.updateRouteStep(4, 'completed') // 完成循环判断
          }
        }

        // 如果是第一条消息，从后端获取最终的会话名称（可能经过后端清理）
        if (isFirstMessage && currentSessionId.value) {
          // 异步获取最新的会话信息，但不阻塞UI
          sessionStore.getSession(currentSessionId.value).then(session => {
            if (session.name && session.name !== sessions.value.find(s => s.id === currentSessionId.value)?.name) {
              sessionStore.updateSessionName(currentSessionId.value!, session.name)
            }
          }).catch(error => {
            console.error('获取会话信息失败:', error)
          })
        }

        nextTick(() => scrollToBottom())
      },
      (error) => {
        // 错误处理
        console.error('对话处理错误:', error)

        // 清除超时保护
        clearTimeout(timeoutId)

        ElMessage.error(`处理消息时出错: ${error}`)
        pushText(`\n\n处理出错: ${error}`)

        // 更新流程图状态为错误
        if (selectedRouteForThisMessage === 'route1') {
          // 如果当前在AI分析阶段出错
          const route1Steps = flowPanelRef.value?.route1Steps || []
          if (route1Steps[1].status === 'active') {
            route1Steps[1].status = 'completed' // 标记AI分析完成（虽然有错误）
            route1Steps[2].status = 'completed' // 尝试完成报告生成
          }
        } else if (selectedRouteForThisMessage === 'route2') {
          // 根据当前进度更新状态
          const route2Steps = flowPanelRef.value?.route2Steps || []
          for (let i = 0; i < route2Steps.length; i++) {
            if (route2Steps[i].status === 'active') {
              route2Steps[i].status = 'completed'
              break
            }
          }
        }

        nextTick(() => scrollToBottom())
      },
      flowPanelRef.value?.selectedModel // 传递选择的模型ID
    )

    assistantMessage.loading = false
  } catch (error) {
    console.error('发送消息失败:', error)

    // 清除超时保护
    clearTimeout(timeoutId)

    flowPanelRef.value?.logRouteStatus('发送消息出现错误')

    // 添加错误消息
    messages.value.push({
      type: 'assistant',
      content: [{ type: 'text', content: '抱歉，处理您的请求时出现了错误。请稍后重试。' }],
      timestamp: new Date().toISOString()
    })

    // 确保流程图状态正确结束
    if (selectedRouteForThisMessage === 'route1') {
      flowPanelRef.value?.updateRouteStep(1, 'completed')
      flowPanelRef.value?.updateRouteStep(2, 'completed')
    } else if (selectedRouteForThisMessage === 'route2') {
      flowPanelRef.value?.updateRouteStep(1, 'completed')
      flowPanelRef.value?.updateRouteStep(2, 'completed')
      flowPanelRef.value?.updateRouteStep(4, 'completed')
    }

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
  if (currentSessionId) {
    refreshChatHistory()
  }
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
          <span class="session-name">{{ session.name || `会话 ${session.id.slice(0, 8)}` }}</span>
          <div class="session-actions">
            <el-button type="text" :icon="Edit" size="small" class="action-btn"
              @click.stop="openEditSessionDialog(session.id, session.name || `会话 ${session.id.slice(0, 8)}`)" />
            <el-button type="text" :icon="Delete" size="small" class="action-btn"
              @click.stop="confirmDeleteSession(session.id, session.name || `会话 ${session.id.slice(0, 8)}`)"
              :loading="sessionStore.isDeleting[session.id]" :disabled="sessionStore.isDeleting[session.id]" />
          </div>
        </div>
      </div>
    </div>

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
          <el-button @click="isFlowPanelOpen = !isFlowPanelOpen" :icon="Monitor" text class="toggle-btn">
            流程图
          </el-button>
        </div>
      </div>

      <!-- Chat Messages -->
      <div class="chat-messages" ref="messagesContainer">
        <div v-if="!currentSessionId || !currentDataset" class="empty-state">
          <div class="empty-message">
            <p>选择一个数据集，开始您的数据分析对话</p>
          </div>
        </div>
        <div v-else-if="!messages.length" class="empty-state">
          <div class="empty-message">
            <p>输入分析需求，开始您的数据分析对话</p>
          </div>
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

      <!-- Chat Input Area -->
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
              <el-icon>
                <DocumentCopy />
              </el-icon>
              当前数据集: <strong>{{ turncateString(currentDataset.name || currentDataset.id, 12) }}</strong>
              <el-link type="primary" @click="goToAddData" :underline="false">
                <el-icon>
                  <Edit />
                </el-icon>
                更换
              </el-link>
            </template>
            <template v-else>
              <el-icon>
                <WarningFilled />
              </el-icon>
              <el-link type="warning" @click="goToAddData" :underline="false">
                请先选择一个数据集进行分析
              </el-link>
            </template>
          </div>
          <el-divider direction="vertical" style="margin: 0 8px;" />
          <div class="quick-prompt-tags">
            <el-tag class="action-tag" @click="addSampleQuestion('分析数据的基本统计信息')">
              <el-icon>
                <DataAnalysis />
              </el-icon>
              基本统计
            </el-tag>
            <el-tag class="action-tag" @click="addSampleQuestion('绘制各列的相关性热力图')">
              <el-icon>
                <PieChart />
              </el-icon>
              相关性分析
            </el-tag>
            <el-tag class="action-tag" @click="addSampleQuestion('检测并可视化异常值')">
              <el-icon>
                <Search />
              </el-icon>
              异常检测
            </el-tag>
            <el-tag class="action-tag" @click="addSampleQuestion('生成数据质量报告')">
              <el-icon>
                <Document />
              </el-icon>
              质量报告
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- Flow Panel -->
    <FlowPanel v-model:is-flow-panel-open="isFlowPanelOpen" ref="flowPanelRef"></FlowPanel>

    <!-- Select Dataset Dialog -->
    <el-dialog v-model="selectDatasetDialogVisible" title="选择数据集以创建会话" width="600px">
      <el-empty v-if="!Object.keys(dataSourceStore.dataSources).length" description="暂无数据集，请先上传或选择一个数据集。">
        <el-button type="primary" @click="goToAddData">前往添加数据集</el-button>
      </el-empty>
      <div v-else class="dataset-list">
        <div v-for="[sourceId, metadata] in Object.entries(dataSourceStore.dataSources)" :key="sourceId"
          class="dataset-item" @click="createNewSession(sourceId)">
          <div class="dataset-info">
            <el-icon>
              <DocumentCopy />
            </el-icon>
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

    <!-- 会话编辑对话框 -->
    <el-dialog v-model="editSessionDialogVisible" title="编辑会话名称" width="400px" destroy-on-close>
      <div class="edit-session-dialog">
        <el-form :model="{ name: editingSessionName }" label-position="top">
          <el-form-item label="会话名称">
            <el-input v-model="editingSessionName" placeholder="请输入会话名称" maxlength="50" show-word-limit clearable
              autofocus />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="editSessionDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveSessionEdit" :disabled="!editingSessionName.trim()">保存</el-button>
        </div>
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

      &.delete-btn:hover {
        color: #ef4444;
        background-color: #fef2f2;
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
  padding: 12px 20px 6px;
  background-color: #ffffff;
  border-top: 1px solid #e5e7eb;
}

.chat-input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  margin-bottom: 12px;

  .el-textarea {
    flex: 1;
  }

  .send-button {
    flex-shrink: 0;
    height: 32px;
    padding: 0 16px;
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

.edit-session-dialog {
  padding: 10px;

  .el-form-item__label {
    font-weight: 500;
    color: #374151;
  }

  .el-input {
    .el-input__wrapper {
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
      transition: all 0.3s ease;

      &:hover,
      &:focus {
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1), 0 0 0 1px #10b981;
      }
    }
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;

  .el-button {
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 500;
    transition: all 0.3s ease;

    &--primary {
      background-color: #10b981;
      border-color: #10b981;

      &:hover {
        background-color: #059669;
        border-color: #059669;
        transform: translateY(-1px);
      }

      &:disabled {
        background-color: #d1fae5;
        border-color: #d1fae5;
      }
    }
  }
}
</style>
