<script setup lang="ts">
import AssistantMessage from '@/components/AssistantMessage.vue';
import { useDataSourceStore } from '@/stores/datasource';
import { useSessionStore } from '@/stores/session';
import { useModelStore } from '@/stores/model';
import type { AssistantChatMessage, AssistantChatMessageContent, AssistantChatMessageText, ChatMessage } from '@/types';
import { ChatDotRound, DArrowLeft, DArrowRight, DataAnalysis, Delete, Document, DocumentCopy, Edit, PieChart, Plus, Search, WarningFilled, Monitor, Setting, Loading, CircleCheck, Clock } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, nextTick, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

// 流程图步骤类型定义
interface FlowStep {
  id: string
  title: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  timestamp: Date
  details?: string[]
  error?: string
}

type ChatMessageWithSuggestions = ChatMessage & { loading?: boolean, suggestions?: string[] }

const router = useRouter()
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();
const modelStore = useModelStore();

// --- State for new UI ---
const isSidebarOpen = ref(true)

const userInput = ref<string>('')
const messages = ref<ChatMessageWithSuggestions[]>([])
const messagesContainer = ref<HTMLElement | null>(null)
const isProcessingChat = ref<boolean>(false)
const selectDatasetDialogVisible = ref<boolean>(false)
const isFlowPanelOpen = ref<boolean>(true) // 控制流程图面板的显示/隐藏
const isDeletingSession = ref<boolean>(false) // 防止重复删除操作

// 固定路线配置
const selectedRoute = ref<string>('route1') // 当前选中的路线
const currentRouteReason = ref<string>('') // 当前路线选择的原因

// 路线1：生成总体报告的步骤
const route1Steps = ref([
  { title: '用户输入', description: '接收用户的查询请求', status: 'pending' },
  { title: 'AI分析处理', description: '智能分析用户需求和数据', status: 'pending' },
  { title: '生成报告', description: '生成完整的数据分析报告', status: 'pending' }
])

// 路线2：其他处理的步骤
const route2Steps = ref([
  { title: '用户输入', description: '接收用户的查询请求', status: 'pending' },
  { title: 'AI分析处理', description: '智能分析用户需求', status: 'pending' },
  { title: '判断执行工具', description: '分析并选择合适的处理工具', status: 'pending' },
  { title: '调用执行工具', description: '执行相应的数据处理工具', status: 'pending' },
  { title: '是否进行循环', description: '判断是否需要继续处理', status: 'pending' }
])

// 流程图相关状态 (保留原有的flowSteps以兼容现有代码)
const flowSteps = ref<FlowStep[]>([])

// 模型配置相关状态
const availableModels = computed(() => modelStore.availableModels)
const selectedModel = computed({
  get: () => modelStore.selectedModel?.id || 'gemini-2.0-flash',
  set: (value: string) => {
    const model = availableModels.value.find(m => m.id === value)
    if (model) {
      modelStore.setSelectedModel(model)
    }
  }
})

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
  messages.value = session.chat_history.map((entry) => [entry.user_message, {
    ...entry.assistant_response,
    content: mergeTextPart(entry.assistant_response.content),
  }]).flat() || []
  scrollToBottom()
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
      clearFlowSteps()

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

// 流程图管理方法
const addFlowStep = (step: Omit<FlowStep, 'id' | 'timestamp'>) => {
  const newStep: FlowStep = {
    ...step,
    id: `step-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: new Date()
  }
  flowSteps.value.push(newStep)
  return newStep.id
}

const updateFlowStep = (stepId: string, updates: Partial<FlowStep>) => {
  const stepIndex = flowSteps.value.findIndex(step => step.id === stepId)
  if (stepIndex !== -1) {
    flowSteps.value[stepIndex] = { ...flowSteps.value[stepIndex], ...updates }
  }
}

const clearFlowSteps = () => {
  flowSteps.value = []
}

// 模型配置方法
const changeModel = (modelId: string) => {
  selectedModel.value = modelId
  const model = availableModels.value.find(m => m.id === modelId)

  // 添加模型切换步骤到流程图
  addFlowStep({
    title: '模型切换',
    description: `切换到模型: ${model?.name || modelId}`,
    status: 'completed'
  })

  ElMessage.success(`已切换到模型: ${model?.name || modelId}`)
}

const getCurrentModelInfo = computed(() => {
  return modelStore.selectedModel || availableModels.value[0] || { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', provider: 'Google' }
})

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
  const selectedRouteForThisMessage = autoSelectRoute(userMessage)

  // 更新固定路线步骤状态
  // 第一步：用户输入
  logRouteStatus('开始处理用户输入')
  updateRouteStep(0, 'completed')

  // 第二步：AI分析处理
  updateRouteStep(1, 'active')

  // 设置超时保护，防止流程图永远卡在AI分析阶段
  const timeoutId = setTimeout(() => {
    console.warn('AI分析处理超时，强制完成流程图步骤')
    if (selectedRouteForThisMessage === 'route1') {
      updateRouteStep(1, 'completed')
      updateRouteStep(2, 'completed')
    } else {
      updateRouteStep(1, 'completed')
      updateRouteStep(2, 'completed')
      updateRouteStep(4, 'completed')
    }
    logRouteStatus('超时保护：强制完成流程')
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
            if (content.length > 50 && route1Steps.value[1]?.status === 'active') {
              console.log('路线1：AI分析达到50字符，标记为完成')
              updateRouteStep(1, 'completed') // AI分析处理完成
              updateRouteStep(2, 'active')    // 开始生成报告
            }
            if (content.length > 200 && route1Steps.value[2]?.status === 'active') {
              console.log('路线1：内容达到200字符，报告生成完成')
              updateRouteStep(2, 'completed') // 生成报告完成
            }
          } else if (selectedRouteForThisMessage === 'route2') {
            // 路线2：如果还没有工具调用，可能是纯文本回复
            if (content.length > 50 && (!assistantMessage.tool_calls || Object.keys(assistantMessage.tool_calls).length === 0)) {
              console.log('路线2：纯文本回复，完成相应步骤')
              updateRouteStep(1, 'completed') // AI分析处理完成
              updateRouteStep(2, 'completed') // 判断执行工具完成（决定不需要工具）
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
          updateRouteStep(1, 'completed') // AI分析处理完成
          updateRouteStep(2, 'completed') // 判断执行工具完成
          updateRouteStep(3, 'active')    // 调用执行工具开始
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
          updateRouteStep(3, 'completed') // 调用执行工具完成
          updateRouteStep(4, 'active')    // 是否进行循环

          // 自动完成循环判断步骤（默认不循环）
          setTimeout(() => {
            updateRouteStep(4, 'completed') // 完成循环判断
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
        logRouteStatus('对话处理完成')

        // 根据路线和当前状态更新步骤
        if (selectedRouteForThisMessage === 'route1') {
          console.log('执行路线1完成逻辑')
          // 路线1：如果AI分析还在进行中，先完成它，然后完成生成报告
          updateRouteStep(1, 'completed') // AI分析处理完成
          updateRouteStep(2, 'completed') // 生成报告完成
        } else if (selectedRouteForThisMessage === 'route2') {
          console.log('执行路线2完成逻辑')
          // 路线2：检查当前状态并完成剩余步骤
          if (!assistantMessage.tool_calls || Object.keys(assistantMessage.tool_calls).length === 0) {
            console.log('路线2：没有工具调用')
            // 没有工具调用的情况
            updateRouteStep(1, 'completed') // AI分析处理完成
            updateRouteStep(2, 'completed') // 判断执行工具完成（决定不需要工具）
            updateRouteStep(4, 'completed') // 直接完成，不进行循环
          } else {
            console.log('路线2：有工具调用')
            // 有工具调用的情况，确保最后一步完成
            updateRouteStep(4, 'completed') // 完成循环判断
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
          if (route1Steps.value[1].status === 'active') {
            route1Steps.value[1].status = 'completed' // 标记AI分析完成（虽然有错误）
            route1Steps.value[2].status = 'completed' // 尝试完成报告生成
          }
        } else if (selectedRouteForThisMessage === 'route2') {
          // 根据当前进度更新状态
          for (let i = 0; i < route2Steps.value.length; i++) {
            if (route2Steps.value[i].status === 'active') {
              route2Steps.value[i].status = 'completed'
              break
            }
          }
        }

        nextTick(() => scrollToBottom())
      },
      selectedModel.value // 传递选择的模型ID
    )

    assistantMessage.loading = false
  } catch (error) {
    console.error('发送消息失败:', error)

    // 清除超时保护
    clearTimeout(timeoutId)

    logRouteStatus('发送消息出现错误')

    // 添加错误消息
    messages.value.push({
      type: 'assistant',
      content: [{ type: 'text', content: '抱歉，处理您的请求时出现了错误。请稍后重试。' }],
      timestamp: new Date().toISOString()
    })

    // 确保流程图状态正确结束
    if (selectedRouteForThisMessage === 'route1') {
      updateRouteStep(1, 'completed')
      updateRouteStep(2, 'completed')
    } else if (selectedRouteForThisMessage === 'route2') {
      updateRouteStep(1, 'completed')
      updateRouteStep(2, 'completed')
      updateRouteStep(4, 'completed')
    }

    await nextTick()
    scrollToBottom()
  } finally {
    isProcessingChat.value = false
  }
}

// 路线切换处理
const handleRouteChange = (route: string) => {
  console.log('切换到路线:', route)
  logRouteStatus(`切换到${route}`)
  // 重置所有步骤状态
  resetAllSteps()
  logRouteStatus('重置步骤状态完成')
}

// 重置所有路线步骤状态
const resetAllSteps = () => {
  route1Steps.value.forEach(step => {
    step.status = 'pending'
  })
  route2Steps.value.forEach(step => {
    step.status = 'pending'
  })
}

// 更新当前路线的步骤状态
const updateRouteStep = (stepIndex: number, status: 'pending' | 'active' | 'completed') => {
  const oldStatus = selectedRoute.value === 'route1'
    ? route1Steps.value[stepIndex]?.status
    : route2Steps.value[stepIndex]?.status

  if (selectedRoute.value === 'route1' && route1Steps.value[stepIndex]) {
    route1Steps.value[stepIndex].status = status
    console.log(`[流程图] 路线1步骤${stepIndex + 1}状态更新: ${oldStatus} -> ${status}`)
  } else if (selectedRoute.value === 'route2' && route2Steps.value[stepIndex]) {
    route2Steps.value[stepIndex].status = status
    console.log(`[流程图] 路线2步骤${stepIndex + 1}状态更新: ${oldStatus} -> ${status}`)
  }

  logRouteStatus(`步骤${stepIndex + 1}状态更新为${status}`)
}

// 调试函数：监控流程图状态
const logRouteStatus = (message: string) => {
  console.log(`[流程图调试] ${message}`)
  console.log('当前路线:', selectedRoute.value)
  if (selectedRoute.value === 'route1') {
    console.log('路线1状态:', route1Steps.value.map(step => `${step.title}: ${step.status}`))
  } else {
    console.log('路线2状态:', route2Steps.value.map(step => `${step.title}: ${step.status}`))
  }
}

// 测试智能路线选择功能
const testRouteSelection = () => {
  const testCases = [
    "生成完整报告",
    "创建数据分析报告",
    "给我一个综合分析",
    "绘制相关性热力图",
    "计算统计信息",
    "分析数据质量"
  ]

  console.log('=== 智能路线选择测试 ===')
  testCases.forEach(testCase => {
    const route = selectRouteAutomatically(testCase)
    const reason = getRouteSelectionReason(testCase, route)
    console.log(`输入: "${testCase}" -> 路线: ${route} (${reason})`)
  })
  console.log('=== 测试完成 ===')
}

// 智能路线选择函数
const selectRouteAutomatically = (userMessage: string): 'route1' | 'route2' => {
  const message = userMessage.toLowerCase()

  // 路线1关键词：报告生成相关
  const route1Keywords = [
    '报告', '总结', '概述', '汇总', '分析报告', '数据报告',
    '整体分析', '全面分析', '综合分析', '统计报告',
    '生成报告', '创建报告', '制作报告', '输出报告',
    '完整报告', '详细报告', '综合报告', '总体报告',
    '分析结果', '数据总结', '统计总结', '整体情况',
    'report', 'summary', 'overview', 'analysis report',
    'comprehensive', 'complete report', 'detailed report'
  ]

  // 路线2关键词：具体操作、工具使用相关
  const route2Keywords = [
    '绘制', '画图', '图表', '可视化', '图像', '图片',
    '计算', '统计', '筛选', '过滤', '查询', '搜索',
    '清洗', '处理', '转换', '操作', '执行', '运行',
    '热力图', '散点图', '柱状图', '折线图', '饼图',
    'plot', 'chart', 'graph', 'visualization', 'draw',
    'calculate', 'filter', 'query', 'clean', 'process'
  ]

  // 检查是否包含路线1关键词
  const hasRoute1Keywords = route1Keywords.some(keyword => message.includes(keyword))

  // 检查是否包含路线2关键词
  const hasRoute2Keywords = route2Keywords.some(keyword => message.includes(keyword))

  // 决策逻辑
  if (hasRoute1Keywords && !hasRoute2Keywords) {
    return 'route1'
  } else if (hasRoute2Keywords && !hasRoute1Keywords) {
    return 'route2'
  } else if (hasRoute1Keywords && hasRoute2Keywords) {
    // 如果同时包含，根据优先级判断
    // 如果明确提到"报告"，优先选择路线1
    if (message.includes('报告') || message.includes('report')) {
      return 'route1'
    }
    return 'route2'
  } else {
    // 默认情况：如果都不包含特定关键词，根据消息长度和复杂度判断
    // 简短的问题通常是具体操作，长的问题通常需要综合分析
    if (message.length > 100 || message.includes('分析') || message.includes('怎么') || message.includes('如何')) {
      return 'route1'
    }
    return 'route2'
  }
}

// 获取路线选择的原因说明
const getRouteSelectionReason = (userMessage: string, selectedRoute: 'route1' | 'route2'): string => {
  const message = userMessage.toLowerCase()

  if (selectedRoute === 'route1') {
    if (message.includes('报告') || message.includes('report')) {
      return '检测到报告生成需求'
    } else if (message.includes('分析') || message.includes('总结') || message.includes('概述')) {
      return '检测到综合分析需求'
    } else if (message.length > 100) {
      return '复杂查询，适合生成综合报告'
    } else {
      return '默认使用报告生成模式'
    }
  } else {
    if (message.includes('绘制') || message.includes('图表') || message.includes('可视化')) {
      return '检测到可视化需求'
    } else if (message.includes('计算') || message.includes('统计') || message.includes('筛选')) {
      return '检测到数据处理需求'
    } else if (message.includes('热力图') || message.includes('散点图') || message.includes('柱状图')) {
      return '检测到特定图表需求'
    } else {
      return '检测到具体操作需求'
    }
  }
}

// 自动路线选择并更新UI
const autoSelectRoute = (userMessage: string) => {
  const previousRoute = selectedRoute.value
  const newRoute = selectRouteAutomatically(userMessage)
  const reason = getRouteSelectionReason(userMessage, newRoute)

  currentRouteReason.value = reason

  if (newRoute !== previousRoute) {
    selectedRoute.value = newRoute
    resetAllSteps()
    logRouteStatus(`自动切换路线：${previousRoute} -> ${newRoute} (${reason})`)
    console.log(`[智能路线选择] 用户输入: "${userMessage}"`)
    console.log(`[智能路线选择] 选择路线: ${newRoute}`)
    console.log(`[智能路线选择] 选择原因: ${reason}`)
  } else {
    logRouteStatus(`保持当前路线: ${newRoute} (${reason})`)
  }

  return newRoute
}

// 手动切换路线
const toggleRouteManually = () => {
  const currentRoute = selectedRoute.value
  const newRoute = currentRoute === 'route1' ? 'route2' : 'route1'

  selectedRoute.value = newRoute
  resetAllSteps()

  console.log(`[手动路线切换] ${currentRoute} -> ${newRoute}`)
  logRouteStatus(`手动切换路线到: ${newRoute}`)

  ElMessage.info(`已手动切换到路线: ${newRoute === 'route1' ? '生成总体报告' : '其他处理'}`)
}

// 检查是否有活跃步骤
const hasActiveSteps = computed(() => {
  if (selectedRoute.value === 'route1') {
    return route1Steps.value.some(step => step.status === 'active')
  } else {
    return route2Steps.value.some(step => step.status === 'active')
  }
})

// 强制完成流程
const forceCompleteFlow = () => {
  console.log('用户强制完成流程')

  if (selectedRoute.value === 'route1') {
    route1Steps.value.forEach(step => {
      if (step.status === 'active' || step.status === 'pending') {
        step.status = 'completed'
      }
    })
  } else {
    route2Steps.value.forEach(step => {
      if (step.status === 'active' || step.status === 'pending') {
        step.status = 'completed'
      }
    })
  }

  logRouteStatus('用户强制完成所有流程步骤')
  ElMessage.success('流程已强制完成')
}

// --- Lifecycle Hooks ---
onMounted(async () => {
  await loadSessions()
  await dataSourceStore.listDataSources() // 加载数据源
  await modelStore.fetchAvailableModels() // 获取可用模型

  // 运行路线选择测试
  testRouteSelection()

  // 初始化模型配置
  addFlowStep({
    title: '系统初始化',
    description: `默认模型已设置为 ${getCurrentModelInfo.value.name}`,
    status: 'completed',
    details: [
      `模型: ${getCurrentModelInfo.value.name}`,
      `提供商: ${getCurrentModelInfo.value.provider}`,
      `模型ID: ${selectedModel.value}`
    ]
  })

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
          <span class="session-name">{{ session.name }}</span>
          <div class="session-actions">
            <el-button type="text" :icon="Edit" size="small" class="action-btn" />
            <el-button
              type="text"
              :icon="Delete"
              size="small"
              class="action-btn delete-btn"
              @click="deleteSession(session.id, $event)"
              :disabled="isDeletingSession"
              title="删除会话"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Chat Panel -->
    <div class="chat-panel">
      <div class="chat-panel-header">
        <div class="header-left">
          <el-button v-if="!isSidebarOpen" @click="isSidebarOpen = true" :icon="DArrowRight" text class="toggle-btn" />
          <span class="session-title" v-if="currentSessionId">
            {{sessions.find(s => s.id === currentSessionId)?.name || `会话: ${currentSessionId.slice(0, 8)}...`}}
          </span>
        </div>
        <div class="header-right">
          <el-button
            @click="isFlowPanelOpen = !isFlowPanelOpen"
            :icon="Monitor"
            text
            class="toggle-btn"
          >
            流程图
          </el-button>
        </div>
      </div>
      <div class="chat-messages" ref="messagesContainer">
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
              <el-icon>
                <DocumentCopy />
              </el-icon>
              当前数据集: <strong>{{ currentDataset.name || currentDataset.id.slice(0, 12) + '...' }}</strong>
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
    <div :class="['flow-panel', { 'is-closed': !isFlowPanelOpen }]">
      <div class="flow-panel-header">
        <span class="panel-title">
          <el-icon><Monitor /></el-icon>
          处理流程
        </span>
        <div class="header-actions">
          <el-button
            @click="forceCompleteFlow"
            size="small"
            type="text"
            class="force-complete-btn"
            title="强制完成流程"
            v-if="hasActiveSteps"
          >
            完成
          </el-button>
          <el-button
            @click="isFlowPanelOpen = false"
            :icon="DArrowRight"
            text
            size="small"
            class="toggle-btn"
          />
        </div>
      </div>

      <!-- 模型配置区域 -->
      <div class="model-config-section">
        <div class="config-header">
          <span class="config-title">
            <el-icon><Setting /></el-icon>
            模型配置
          </span>
        </div>
        <div class="model-selector">
          <el-select
            v-model="selectedModel"
            @change="changeModel"
            placeholder="选择模型"
            size="small"
            class="model-select"
          >
            <el-option-group
              v-for="provider in ['Google', 'OpenAI', 'DeepSeek', 'Anthropic']"
              :key="provider"
              :label="provider"
            >
              <el-option
                v-for="model in availableModels.filter(m => m.provider === provider)"
                :key="model.id"
                :label="model.name"
                :value="model.id"
              >
                <div class="model-option">
                  <span class="model-name">{{ model.name }}</span>
                  <span class="model-provider">{{ model.provider }}</span>
                </div>
              </el-option>
            </el-option-group>
          </el-select>
        </div>
        <div class="current-model-info">
          <span class="current-model">
            当前: {{ getCurrentModelInfo.name }}
          </span>
        </div>
      </div>

      <div class="flow-panel-content">
        <div class="fixed-flow-routes">
          <!-- 路线选择 -->
          <div class="route-selector">
            <div class="route-info">
              <el-icon><Setting /></el-icon>
              <span class="route-label">智能路线选择</span>
              <el-tag size="small" type="info">自动</el-tag>
              <el-button
                type="text"
                size="small"
                @click="toggleRouteManually"
                class="manual-toggle"
                title="手动切换路线"
              >
                <el-icon><Edit /></el-icon>
              </el-button>
            </div>
            <el-radio-group v-model="selectedRoute" @change="handleRouteChange" disabled>
              <el-radio-button label="route1">生成总体报告</el-radio-button>
              <el-radio-button label="route2">其他处理</el-radio-button>
            </el-radio-group>
            <div class="route-description">
              <span v-if="currentRouteReason" class="route-reason">
                {{ currentRouteReason }}
              </span>
              <span v-if="selectedRoute === 'route1'" class="route-desc">
                系统将生成综合数据分析报告
              </span>
              <span v-else class="route-desc">
                系统将执行具体的数据处理操作
              </span>
            </div>
          </div>

          <!-- 路线1：生成总体报告 -->
          <div v-if="selectedRoute === 'route1'" class="flow-route">
            <h4 class="route-title">路线1：生成总体报告</h4>
            <div class="flow-steps">
              <div v-for="(step, index) in route1Steps" :key="index"
                   :class="['flow-step', step.status]">
                <div class="step-number">{{ index + 1 }}</div>
                <div class="step-content">
                  <div class="step-title">{{ step.title }}</div>
                  <div class="step-description">{{ step.description }}</div>
                </div>
                <div class="step-status">
                  <el-icon v-if="step.status === 'active'" class="loading"><Loading /></el-icon>
                  <el-icon v-else-if="step.status === 'completed'" class="completed"><CircleCheck /></el-icon>
                  <el-icon v-else class="pending"><Clock /></el-icon>
                </div>
              </div>
            </div>
          </div>

          <!-- 路线2：其他处理 -->
          <div v-if="selectedRoute === 'route2'" class="flow-route">
            <h4 class="route-title">路线2：其他处理</h4>
            <div class="flow-steps">
              <div v-for="(step, index) in route2Steps" :key="index"
                   :class="['flow-step', step.status]">
                <div class="step-number">{{ index + 1 }}</div>
                <div class="step-content">
                  <div class="step-title">{{ step.title }}</div>
                  <div class="step-description">{{ step.description }}</div>
                </div>
                <div class="step-status">
                  <el-icon v-if="step.status === 'active'" class="loading"><Loading /></el-icon>
                  <el-icon v-else-if="step.status === 'completed'" class="completed"><CircleCheck /></el-icon>
                  <el-icon v-else class="pending"><Clock /></el-icon>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

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
  padding: 16px 24px 24px;
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

// --- Flow Panel Styles ---
.flow-panel {
  width: 320px;
  flex-shrink: 0;
  background: #ffffff;
  border-left: 1px solid #e5e7eb;
  transition: width 0.3s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  &.is-closed {
    width: 0;
  }
}

.flow-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
  flex-shrink: 0;

  .panel-title {
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
    color: #374151;
    font-size: 12px;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .force-complete-btn {
    color: #f59e0b;
    padding: 2px 6px;
    font-size: 10px;

    &:hover {
      color: #d97706;
      background-color: #fef3c7;
    }
  }

  .toggle-btn {
    color: #6b7280;
    padding: 2px;
    border-radius: 3px;
    transition: all 0.2s ease;

    &:hover {
      color: #374151;
      background-color: #e5e7eb;
    }
  }
}

.flow-panel-content {
  flex: 1;
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

// --- Model Config Styles ---
.model-config-section {
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;

  .config-header {
    margin-bottom: 8px;

    .config-title {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      font-weight: 600;
      color: #374151;
    }
  }

  .model-selector {
    margin-bottom: 6px;

    .model-select {
      width: 100%;

      :deep(.el-input) {
        height: 28px;

        .el-input__inner {
          font-size: 11px;
          height: 28px;
          line-height: 28px;
          padding: 0 8px;
        }
      }

      :deep(.el-select__popper) {
        .el-option-group__title {
          font-size: 10px;
          padding: 4px 8px;
          color: #6b7280;
          font-weight: 600;
        }
      }
    }
  }

  .model-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .model-name {
      font-size: 11px;
      color: #374151;
      flex: 1;
    }

    .model-provider {
      font-size: 9px;
      color: #9ca3af;
      background: #f3f4f6;
      padding: 1px 4px;
      border-radius: 3px;
      margin-left: 8px;
    }
  }

  .current-model-info {
    .current-model {
      font-size: 10px;
      color: #10b981;
      font-weight: 500;
      background: #f0fdf4;
      padding: 2px 6px;
      border-radius: 3px;
      border: 1px solid #bbf7d0;
      display: inline-block;
      width: 100%;
      text-align: center;
    }
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

// --- Fixed Flow Routes Styles ---
.fixed-flow-routes {
  padding: 0;  .route-selector {
    padding: 12px;
    border-bottom: 1px solid #e5e7eb;
    background: #f8fafc;

    .route-info {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 8px;
      font-size: 11px;
      color: #6b7280;

      .route-label {
        flex: 1;
        font-weight: 500;
      }

      .manual-toggle {
        padding: 2px 4px;
        font-size: 10px;
        color: #6b7280;

        &:hover {
          color: #3b82f6;
          background-color: #eff6ff;
        }
      }
    }

    .el-radio-group {
      width: 100%;
      margin-bottom: 6px;

      .el-radio-button {
        flex: 1;

        :deep(.el-radio-button__inner) {
          width: 100%;
          font-size: 11px;
          padding: 6px 8px;
          border-radius: 6px;

          &:disabled {
            background-color: #f3f4f6;
            border-color: #d1d5db;
            color: #6b7280;
          }
        }

        &.is-active :deep(.el-radio-button__inner) {
          background-color: #3b82f6;
          border-color: #3b82f6;
          color: white;
        }
      }
    }

    .route-description {
      .route-reason {
        font-size: 10px;
        color: #3b82f6;
        font-weight: 500;
        display: block;
        margin-bottom: 2px;
      }

      .route-desc {
        font-size: 10px;
        color: #9ca3af;
        font-style: italic;
      }
    }
  }

  .flow-route {
    padding: 12px;

    .route-title {
      font-size: 12px;
      font-weight: 600;
      color: #374151;
      margin: 0 0 12px 0;
      padding: 6px 8px;
      background: #f3f4f6;
      border-radius: 6px;
      border-left: 3px solid #3b82f6;
    }

    .flow-steps {
      .flow-step {
        display: flex;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #f1f5f9;
        transition: all 0.3s ease;

        &:last-child {
          border-bottom: none;
        }

        &.pending {
          opacity: 0.6;

          .step-number {
            background: #e5e7eb;
            color: #6b7280;
          }
        }

        &.active {
          background: #eff6ff;
          border-radius: 6px;
          padding: 8px;
          margin: 2px 0;

          .step-number {
            background: #3b82f6;
            color: white;
            animation: pulse 1.5s infinite;
          }

          .step-title {
            color: #1e40af;
            font-weight: 600;
          }
        }

        &.completed {
          .step-number {
            background: #10b981;
            color: white;
          }

          .step-title {
            color: #059669;
            font-weight: 500;
          }
        }

        .step-number {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #e5e7eb;
          color: #6b7280;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          font-weight: 600;
          flex-shrink: 0;
          margin-right: 8px;
          transition: all 0.3s ease;
        }

        .step-content {
          flex: 1;
          min-width: 0;

          .step-title {
            font-size: 11px;
            font-weight: 500;
            color: #374151;
            margin-bottom: 2px;
          }

          .step-description {
            font-size: 10px;
            color: #6b7280;
            line-height: 1.3;
          }
        }

        .step-status {
          margin-left: 8px;
          flex-shrink: 0;

          .el-icon {
            font-size: 14px;

            &.loading {
              color: #3b82f6;
              animation: rotating 1s linear infinite;
            }

            &.completed {
              color: #10b981;
            }

            &.pending {
              color: #9ca3af;
            }
          }
        }
      }
    }
  }
}

@keyframes pulse {
  0%, 100% {
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
</style>
