import { useSessionStore } from '@/stores/session';
import type {
  AssistantChatMessage,
  AssistantChatMessageContent,
  AssistantChatMessageText,
  ChatMessage,
  DataSourceMetadata,
} from '@/types';
import type { FlowPanel } from '@/types/flow';
import { ElMessage } from 'element-plus';
import { nextTick, reactive, ref } from 'vue';

type MessageExtraState = { loading?: boolean; suggestions?: string[] };
type ChatMessageWithSuggestions = ChatMessage & MessageExtraState;
type AssistantChatMessageWithSuggestions = AssistantChatMessage & MessageExtraState;

/**
 * 合并文本部分，将连续的文本消息合并为一个
 */
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
};

/**
 * 从文本中提取建议
 */
const extractSuggestions = (content: string): string[] => {
  // 兼容"**下一步建议**"或"**下一步行动建议**"后有冒号、空行，提取后续所有内容直到下一个空行或结尾
  const match = content.match(
    /\*?\*?(下一步建议|下一步行动建议)\*?\*?[:：]?\s*\n*([\s\S]*?)(?=\n{2,}|$)/,
  );
  if (!match) return [];

  // 只提取第一个有序列表（1. ...）开始的所有有序条目
  const lines = match[2].split('\n');
  const suggestions: string[] = [];
  let inList = false;

  for (const line of lines) {
    if (/^\d+\.\s+/.test(line)) {
      inList = true;
      suggestions.push(line.replace(/^\d+\.\s+/, '').trim());
    } else if (inList && !line.trim()) {
      // 有序列表后遇到空行则停止
      break;
    } else if (inList && !/^\d+\.\s+/.test(line)) {
      // 有序列表中遇到非有序项也停止
      break;
    }
  }

  return suggestions;
};

const fakeFlowPanel = {
  route1Steps: ref([]),
  route2Steps: ref([]),
  selectedModel: ref(''),
  clearFlowSteps: () => {},
  updateRouteStep: (_: number, __: 'active' | 'completed') => {},
  autoSelectRoute: (_: string): 'route1' | 'route2' => 'route1',
  logRouteStatus: (_: string) => {},
} as FlowPanel;

export const useChat = (flowPanelRef?: () => FlowPanel | undefined) => {
  const sessionStore = useSessionStore();
  const messages = ref<ChatMessageWithSuggestions[]>([]);
  const isProcessingChat = ref<boolean>(false);

  /**
   * 刷新聊天历史
   */
  const refreshChatHistory = async (sessionId?: string) => {
    if (!sessionId) return;

    try {
      const session = await sessionStore.getSession(sessionId);
      messages.value =
        session.chat_history
          .map((entry) => {
            const assistantMessage = {
              ...entry.assistant_response,
              content: mergeTextPart(entry.assistant_response.content),
            };

            // 重新提取建议按钮（页面刷新后恢复建议）
            const mergedContent = assistantMessage.content
              .map((c) => (c.type === 'text' ? c.content : ''))
              .join('');

            const suggestions = extractSuggestions(mergedContent);
            if (suggestions.length > 0) {
              (assistantMessage as any).suggestions = suggestions;
            }

            return [entry.user_message, assistantMessage];
          })
          .flat() || [];
    } catch (error) {
      console.error('加载聊天历史失败:', error);
      ElMessage.error('加载聊天历史失败');
    }
  };

  /**
   * 发送消息
   */
  const sendMessage = async (
    userMessage: string,
    currentSessionId: string | null,
    currentDatasets: DataSourceMetadata[] | null,
    scrollToBottom: () => void,
  ): Promise<void> => {
    if (!userMessage.trim()) return;

    if (!currentDatasets) {
      ElMessage.warning('请先选择或上传一个数据集。');
      return;
    }

    if (isProcessingChat.value) return;

    isProcessingChat.value = true;
    const isFirstMessage = messages.value.length === 0; // 检查是否为第一条消息

    // 如果是第一条消息，立即更新会话名称
    if (isFirstMessage && currentSessionId) {
      const sessionName =
        userMessage.length > 30 ? userMessage.substring(0, 30) + '...' : userMessage;
      sessionStore.updateSessionName(currentSessionId, sessionName);
    }

    // 智能路线选择
    const flowPanel = flowPanelRef?.() || fakeFlowPanel;
    const selectedRouteForThisMessage = flowPanel.autoSelectRoute(userMessage);

    // 更新固定路线步骤状态
    // 第一步：用户输入
    flowPanel.logRouteStatus('开始处理用户输入');
    flowPanel.updateRouteStep(0, 'completed');

    // 第二步：AI分析处理
    flowPanel.updateRouteStep(1, 'active');

    // 设置超时保护，防止流程图永远卡在AI分析阶段
    const timeoutId = setTimeout(() => {
      console.warn('AI分析处理超时，强制完成流程图步骤');
      if (selectedRouteForThisMessage === 'route1') {
        flowPanel.updateRouteStep(1, 'completed');
        flowPanel.updateRouteStep(2, 'completed');
      } else {
        flowPanel.updateRouteStep(1, 'completed');
        flowPanel.updateRouteStep(2, 'completed');
        flowPanel.updateRouteStep(4, 'completed');
      }
      flowPanel.logRouteStatus('超时保护：强制完成流程');
    }, 30000); // 30秒超时

    messages.value.push({
      type: 'user',
      content: userMessage,
      timestamp: new Date().toISOString(),
    });

    scrollToBottom?.();

    try {
      // 创建一个初始的空AI回复消息
      const assistantMessage = reactive({
        type: 'assistant',
        content: [],
        timestamp: new Date().toISOString(),
        tool_calls: {},
        loading: true,
        suggestions: [],
      } as AssistantChatMessageWithSuggestions);

      messages.value.push(assistantMessage);

      const pushText = (content: string) => {
        if (
          !assistantMessage.content.length ||
          assistantMessage.content[assistantMessage.content.length - 1].type !== 'text'
        ) {
          assistantMessage.content.push({ type: 'text', content });
          return content;
        }
        const lastText = assistantMessage.content[assistantMessage.content.length - 1] as {
          content: string;
        };
        lastText.content += content;
        return lastText.content;
      };

      // 使用流式API
      await sessionStore.sendStreamChatMessage(
        userMessage,
        (content) => {
          content = pushText(content);

          // 自动提取建议
          const suggestions = extractSuggestions(content);
          if (suggestions.length) {
            assistantMessage.suggestions = suggestions;
          }

          // 如果AI开始输出内容，说明分析阶段基本完成
          if (content.length > 20) {
            if (selectedRouteForThisMessage === 'route1') {
              // 路线1：渐进式推进流程
              if (content.length > 50 && flowPanel.route1Steps.value[1]?.status === 'active') {
                console.log('路线1：AI分析达到50字符，标记为完成');
                flowPanel.updateRouteStep(1, 'completed'); // AI分析处理完成
                flowPanel.updateRouteStep(2, 'active'); // 开始生成报告
              }
              if (content.length > 200 && flowPanel.route1Steps.value[2]?.status === 'active') {
                console.log('路线1：内容达到200字符，报告生成完成');
                flowPanel.updateRouteStep(2, 'completed'); // 生成报告完成
              }
            } else if (selectedRouteForThisMessage === 'route2') {
              // 路线2：如果还没有工具调用，可能是纯文本回复
              if (
                content.length > 50 &&
                (!assistantMessage.tool_calls ||
                  Object.keys(assistantMessage.tool_calls).length === 0)
              ) {
                console.log('路线2：纯文本回复，完成相应步骤');
                flowPanel.updateRouteStep(1, 'completed'); // AI分析处理完成
                flowPanel.updateRouteStep(2, 'completed'); // 判断执行工具完成（决定不需要工具）
              }
            }
          }

          nextTick(() => scrollToBottom?.());
        },
        (id, name, args) => {
          // 工具调用
          if (!assistantMessage.tool_calls) assistantMessage.tool_calls = {};
          assistantMessage.tool_calls[id] = {
            name,
            args,
            status: 'running',
          };
          assistantMessage.content.push({ type: 'tool_call', id });

          // 更新路线步骤：工具调用开始
          if (selectedRouteForThisMessage === 'route2') {
            flowPanel.updateRouteStep(1, 'completed'); // AI分析处理完成
            flowPanel.updateRouteStep(2, 'completed'); // 判断执行工具完成
            flowPanel.updateRouteStep(3, 'active'); // 调用执行工具开始
          }

          nextTick(() => scrollToBottom?.());
        },
        (id, result, artifact) => {
          // 工具结果
          // 更新工具调用状态
          const toolCall = assistantMessage.tool_calls?.[id] || undefined;
          if (toolCall) {
            toolCall.status = 'success';
            toolCall.result = result;
            toolCall.artifact = artifact || null;
          }

          // 工具调用完成，更新路线步骤
          if (selectedRouteForThisMessage === 'route2') {
            flowPanel.updateRouteStep(3, 'completed'); // 调用执行工具完成
            flowPanel.updateRouteStep(4, 'active'); // 是否进行循环

            // 自动完成循环判断步骤（默认不循环）
            setTimeout(() => {
              flowPanel.updateRouteStep(4, 'completed'); // 完成循环判断
            }, 1000);
          }

          nextTick(() => scrollToBottom?.());
        },
        (id, error) => {
          // 工具错误
          // 更新工具调用状态
          const toolCall = assistantMessage.tool_calls?.[id] || undefined;
          if (toolCall) {
            toolCall.status = 'error';
            toolCall.error = error;
          }

          nextTick(() => scrollToBottom?.());
        },
        () => {
          // 完成处理
          console.log('对话完成');
          console.log('selectedRouteForThisMessage:', selectedRouteForThisMessage);
          console.log('assistantMessage.tool_calls:', assistantMessage.tool_calls);

          // 清除超时保护
          clearTimeout(timeoutId);

          assistantMessage.loading = false;
          flowPanel.logRouteStatus('对话处理完成');

          // 根据路线和当前状态更新步骤
          if (selectedRouteForThisMessage === 'route1') {
            console.log('执行路线1完成逻辑');
            // 路线1：如果AI分析还在进行中，先完成它，然后完成生成报告
            flowPanel.updateRouteStep(1, 'completed'); // AI分析处理完成
            flowPanel.updateRouteStep(2, 'completed'); // 生成报告完成
          } else if (selectedRouteForThisMessage === 'route2') {
            console.log('执行路线2完成逻辑');
            // 路线2：检查当前状态并完成剩余步骤
            if (
              !assistantMessage.tool_calls ||
              Object.keys(assistantMessage.tool_calls).length === 0
            ) {
              console.log('路线2：没有工具调用');
              // 没有工具调用的情况
              flowPanel.updateRouteStep(1, 'completed'); // AI分析处理完成
              flowPanel.updateRouteStep(2, 'completed'); // 判断执行工具完成（决定不需要工具）
              flowPanel.updateRouteStep(4, 'completed'); // 直接完成，不进行循环
            } else {
              console.log('路线2：有工具调用');
              // 有工具调用的情况，确保最后一步完成
              flowPanel.updateRouteStep(4, 'completed'); // 完成循环判断
            }
          }

          // 如果是第一条消息，从后端获取最终的会话名称（可能经过后端清理）
          if (isFirstMessage && currentSessionId) {
            // 异步获取最新的会话信息，但不阻塞UI
            sessionStore
              .getSession(currentSessionId)
              .then((session) => {
                const currentSession = sessionStore.sessions.find((s) => s.id === currentSessionId);
                if (session.name && session.name !== currentSession?.name) {
                  sessionStore.updateSessionName(currentSessionId, session.name);
                }
              })
              .catch((error) => {
                console.error('获取会话信息失败:', error);
              });
          }

          nextTick(() => scrollToBottom?.());
        },
        (error) => {
          // 错误处理
          console.error('对话处理错误:', error);

          // 清除超时保护
          clearTimeout(timeoutId);

          ElMessage.error(`处理消息时出错: ${error}`);
          pushText(`\n\n处理出错: ${error}`);

          // 更新流程图状态为错误
          if (selectedRouteForThisMessage === 'route1') {
            // 如果当前在AI分析阶段出错
            const route1Steps = flowPanel.route1Steps.value || [];
            if (route1Steps[1]?.status === 'active') {
              flowPanel.updateRouteStep(1, 'completed'); // 标记AI分析完成（虽然有错误）
              flowPanel.updateRouteStep(2, 'completed'); // 尝试完成报告生成
            }
          } else if (selectedRouteForThisMessage === 'route2') {
            // 根据当前进度更新状态
            const route2Steps = flowPanel.route2Steps.value || [];
            for (let i = 0; i < route2Steps.length; i++) {
              if (route2Steps[i]?.status === 'active') {
                flowPanel.updateRouteStep(i, 'completed');
                break;
              }
            }
          }

          nextTick(() => scrollToBottom?.());
        },
        flowPanel.selectedModel.value, // 传递选择的模型ID
      );

      assistantMessage.loading = false;
    } catch (error) {
      console.error('发送消息失败:', error);

      // 清除超时保护
      clearTimeout(timeoutId);

      flowPanel.logRouteStatus('发送消息出现错误');

      // 添加错误消息
      messages.value.push({
        type: 'assistant',
        content: [{ type: 'text', content: '抱歉，处理您的请求时出现了错误。请稍后重试。' }],
        timestamp: new Date().toISOString(),
      });

      // 确保流程图状态正确结束
      if (selectedRouteForThisMessage === 'route1') {
        flowPanel.updateRouteStep(1, 'completed');
        flowPanel.updateRouteStep(2, 'completed');
      } else if (selectedRouteForThisMessage === 'route2') {
        flowPanel.updateRouteStep(1, 'completed');
        flowPanel.updateRouteStep(2, 'completed');
        flowPanel.updateRouteStep(4, 'completed');
      }

      nextTick(() => scrollToBottom?.());
    } finally {
      isProcessingChat.value = false;
    }
  };

  return {
    messages,
    isProcessingChat,
    refreshChatHistory,
    sendMessage,
  };
};
