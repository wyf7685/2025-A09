import { useModelStore } from '@/stores/model';
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

// 声明全局类型扩展
declare global {
  interface Window {
    _flowTimeoutIds?: number[];
  }
}

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
      suggestions.push(
        line
          .replace(/^\d+\.\s+/, '')
          .replace('\\_', '_')
          .trim(),
      );
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
  const modelStore = useModelStore();
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

    // 获取流程图引用
    const flowPanel = flowPanelRef?.() || fakeFlowPanel;

    // 在每次对话开始前彻底重置流程图
    console.log('[ChatAgent] 开始新对话，重置流程图...');
    flowPanel.clearFlowSteps();

    // 清除所有可能的超时计时器
    if (window._flowTimeoutIds) {
      window._flowTimeoutIds.forEach((id: number) => clearTimeout(id));
    }
    window._flowTimeoutIds = [];

    // 智能路线选择
    const selectedRouteForThisMessage = flowPanel.autoSelectRoute(userMessage);

    // 更新固定路线步骤状态
    // 第一步：用户输入
    flowPanel.logRouteStatus('开始处理用户输入');
    flowPanel.updateRouteStep(0, 'completed');

    // 第二步：API请求处理
    flowPanel.updateRouteStep(1, 'active');
    flowPanel.logRouteStatus('后端API开始处理请求');

    // 第三步延迟激活：模拟后端处理时间
    const modelSelectionTimeoutId = setTimeout(() => {
      flowPanel.updateRouteStep(1, 'completed');
      // 第三步：LLM模型选择
      flowPanel.updateRouteStep(2, 'active');

      // 获取当前模型信息
      const modelId = modelStore?.selectedModel?.id || 'gemini-2.0-flash';
      const modelName = modelStore?.selectedModel?.name || 'Gemini 2.0 Flash';

      // 设置模型名称到流程图
      if (selectedRouteForThisMessage === 'route1' && flowPanel.route1Steps.value[2]) {
        flowPanel.route1Steps.value[2].toolName = modelName;
      } else if (selectedRouteForThisMessage === 'route2' && flowPanel.route2Steps.value[2]) {
        flowPanel.route2Steps.value[2].toolName = modelName;
      }

      flowPanel.logRouteStatus(`选择并初始化LLM模型: ${modelName}`);
    }, 500);

    // 记录超时ID
    if (!window._flowTimeoutIds) {
      window._flowTimeoutIds = [];
    }
    window._flowTimeoutIds.push(modelSelectionTimeoutId);

    // 设置超时保护，防止流程图永远卡在处理阶段
    const timeoutId = setTimeout(() => {
      console.warn('处理超时，强制完成流程图步骤');
      if (selectedRouteForThisMessage === 'route1') {
        // 路线1超时处理
        for (let i = 1; i <= 4; i++) {
          flowPanel.updateRouteStep(i, 'completed');
        }
      } else {
        // 路线2超时处理
        for (let i = 1; i <= 5; i++) {
          flowPanel.updateRouteStep(i, 'completed');
        }
      }
      flowPanel.logRouteStatus('超时保护：强制完成流程');
    }, 30000); // 30秒超时

    // 记录超时ID，以便在需要时清除
    if (!window._flowTimeoutIds) {
      window._flowTimeoutIds = [];
    }
    window._flowTimeoutIds.push(timeoutId);

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

          // 如果AI开始输出内容，说明处理阶段进行中
          if (content.length > 20) {
            if (selectedRouteForThisMessage === 'route1') {
              // 路线1：渐进式推进流程
              if (content.length > 30 && flowPanel.route1Steps.value[2]?.status === 'active') {
                // LLM模型选择完成
                flowPanel.updateRouteStep(2, 'completed');
                // Agent初始化
                flowPanel.updateRouteStep(3, 'active');
                flowPanel.logRouteStatus('LLM模型选择完成，初始化Agent');
              }
              if (content.length > 100 && flowPanel.route1Steps.value[3]?.status === 'active') {
                // Agent初始化完成
                flowPanel.updateRouteStep(3, 'completed');
                // 开始生成分析报告
                flowPanel.updateRouteStep(4, 'active');
                flowPanel.logRouteStatus('Agent初始化完成，开始生成分析报告');
              }
              if (content.length > 300 && flowPanel.route1Steps.value[4]?.status === 'active') {
                // 分析报告生成完成
                flowPanel.updateRouteStep(4, 'completed');
                flowPanel.logRouteStatus('分析报告生成完成');
              }
            } else if (selectedRouteForThisMessage === 'route2') {
              // 路线2：根据内容进度更新步骤
              if (content.length > 30 && flowPanel.route2Steps.value[2]?.status === 'active') {
                // LLM模型选择完成
                flowPanel.updateRouteStep(2, 'completed');
                // 数据源加载
                flowPanel.updateRouteStep(3, 'active');
                flowPanel.logRouteStatus('LLM模型选择完成，开始加载数据源');

                // 如果没有工具调用，可能是直接文本回复
                if (
                  !assistantMessage.tool_calls ||
                  Object.keys(assistantMessage.tool_calls).length === 0
                ) {
                  const noToolTimeoutId = setTimeout(() => {
                    if (content.length > 100) {
                      flowPanel.updateRouteStep(3, 'completed');
                      flowPanel.logRouteStatus('数据源加载完成，无需工具调用');
                      flowPanel.updateRouteStep(5, 'completed'); // 跳过工具调用，直接完成
                    }
                  }, 1000);

                  // 记录超时ID
                  if (!window._flowTimeoutIds) {
                    window._flowTimeoutIds = [];
                  }
                  window._flowTimeoutIds.push(noToolTimeoutId);
                }
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
            // 确保模型选择阶段完成
            if (flowPanel.route2Steps.value[2]?.status === 'active') {
              flowPanel.updateRouteStep(2, 'completed'); // LLM模型选择完成
            }

            // 确保数据源加载完成
            if (flowPanel.route2Steps.value[3]?.status !== 'completed') {
              flowPanel.updateRouteStep(3, 'completed');
              flowPanel.logRouteStatus('数据源加载完成，开始执行工具');
            }

            // 检查流程图是否处于循环状态
            const isInLoop =
              flowPanel.route2Steps.value[5]?.nextLoop &&
              flowPanel.route2Steps.value[5].nextLoop.length > 0;

            // 设置工具名称 - 正确处理循环情况
            if (flowPanel.route2Steps.value[4]) {
              if (isInLoop) {
                // 如果处于循环中，下一个工具调用应该设置在循环节点中
                // 保留现有工具列表以记录历史
                const existingTools = flowPanel.route2Steps.value[4].toolName || '';
                const toolsList = existingTools ? existingTools.split(', ') : [];

                if (!toolsList.includes(name)) {
                  toolsList.push(name);
                  flowPanel.route2Steps.value[4].toolName = toolsList.join(', ');
                }

                // 同时在循环节点单独设置当前工具
                if (flowPanel.route2Steps.value[5]?.nextLoop?.[0]) {
                  flowPanel.route2Steps.value[5].nextLoop[0].toolName = name;
                  flowPanel.route2Steps.value[5].nextLoop[0].description = `执行相应的数据处理工具（循环）：${name}`;
                }
              } else {
                // 如果不在循环中，正常添加工具名称
                const existingTools = flowPanel.route2Steps.value[4].toolName || '';
                const toolsList = existingTools ? existingTools.split(', ') : [];

                // 如果当前工具不在列表中，则添加
                if (!toolsList.includes(name)) {
                  toolsList.push(name);
                  flowPanel.route2Steps.value[4].toolName = toolsList.join(', ');
                } else if (!existingTools) {
                  // 如果没有现有工具，直接设置
                  flowPanel.route2Steps.value[4].toolName = name;
                }
              }
            }

            // 工具调用开始
            flowPanel.logRouteStatus(`正在执行工具：${name}`);
            flowPanel.updateRouteStep(4, 'active');
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

          // 获取所有已调用的工具名称
          const toolNames = Object.values(assistantMessage.tool_calls || {})
            .map((call) => (call as any).name)
            .filter((name) => !!name);

          // 工具调用完成，更新路线步骤
          if (selectedRouteForThisMessage === 'route2') {
            // 只有当工具步骤处于活动状态时才更新
            if (flowPanel.route2Steps.value[4]?.status === 'active') {
              // 确保工具名称包含所有已执行的工具
              if (flowPanel.route2Steps.value[4]) {
                // 确保当前工具已被包含在工具名称列表中
                const currentName = toolCall?.name || '未知工具';
                const existingTools = flowPanel.route2Steps.value[4].toolName || '';
                const toolsList = existingTools ? existingTools.split(', ') : [];

                // 如果当前工具不在列表中，添加它
                if (currentName && !toolsList.includes(currentName)) {
                  toolsList.push(currentName);
                  flowPanel.route2Steps.value[4].toolName = toolsList.join(', ');
                }
              }

              flowPanel.updateRouteStep(4, 'completed'); // 工具调用完成
              flowPanel.logRouteStatus(`工具 ${toolCall?.name || '未知工具'} 执行完成`);

              // 准备处理下一个工具调用或完成
              if (Object.keys(assistantMessage.tool_calls || {}).length > 1) {
                // 有多个工具调用，需要循环处理
                const toolCallIds = Object.keys(assistantMessage.tool_calls || {});
                const completedTools = Object.values(assistantMessage.tool_calls || {}).filter(
                  (tool) => (tool as any).status === 'success',
                ).length;

                // 还有工具未执行完
                if (completedTools < toolCallIds.length) {
                  flowPanel.updateRouteStep(5, 'active'); // 激活循环判断
                  flowPanel.logRouteStatus('循环：是，需要执行更多工具');

                  // 标记循环完成后，会在下一轮开始执行下一个工具
                  const loopTimeoutId = setTimeout(() => {
                    if (flowPanel.route2Steps.value[5]?.status === 'active') {
                      flowPanel.updateRouteStep(5, 'completed');
                      flowPanel.logRouteStatus('循环：是，继续执行下一个工具');
                    }
                  }, 1000);

                  // 记录超时ID
                  if (!window._flowTimeoutIds) {
                    window._flowTimeoutIds = [];
                  }
                  window._flowTimeoutIds.push(loopTimeoutId);
                } else {
                  // 所有工具都执行完了
                  flowPanel.updateRouteStep(5, 'active');
                  const completeAllTimeoutId = setTimeout(() => {
                    if (flowPanel.route2Steps.value[5]?.status === 'active') {
                      flowPanel.updateRouteStep(5, 'completed');
                      flowPanel.logRouteStatus('全部工具执行完成，不需要继续循环');
                    }
                  }, 1000);

                  // 记录超时ID
                  if (!window._flowTimeoutIds) {
                    window._flowTimeoutIds = [];
                  }
                  window._flowTimeoutIds.push(completeAllTimeoutId);
                }
              } else {
                // 只有一个工具调用，直接激活判断步骤
                flowPanel.updateRouteStep(5, 'active');
                const singleToolTimeoutId = setTimeout(() => {
                  if (flowPanel.route2Steps.value[5]?.status === 'active') {
                    flowPanel.updateRouteStep(5, 'completed');
                    flowPanel.logRouteStatus('工具执行完成，不需要循环');
                  }
                }, 1000);

                // 记录超时ID
                if (!window._flowTimeoutIds) {
                  window._flowTimeoutIds = [];
                }
                window._flowTimeoutIds.push(singleToolTimeoutId);
              }
            }
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

          // 工具调用出错，更新路线步骤
          if (
            selectedRouteForThisMessage === 'route2' &&
            flowPanel.route2Steps.value[3]?.status === 'active'
          ) {
            // 标记工具执行为完成（尽管是出错完成）
            flowPanel.updateRouteStep(3, 'completed');
            flowPanel.logRouteStatus(`工具执行出错：${error}`);

            // 移动到下一步
            flowPanel.updateRouteStep(4, 'active');
            const errorTimeoutId = setTimeout(() => {
              if (flowPanel.route2Steps.value[4]?.status === 'active') {
                flowPanel.updateRouteStep(4, 'completed');
                flowPanel.logRouteStatus('判断完成：不需要循环');
              }
            }, 1000);

            // 记录超时ID
            if (!window._flowTimeoutIds) {
              window._flowTimeoutIds = [];
            }
            window._flowTimeoutIds.push(errorTimeoutId);
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
            // 路线1：检查并确保所有步骤都已完成
            const route1Steps = flowPanel.route1Steps.value || [];

            if (route1Steps[1]?.status !== 'completed') {
              flowPanel.updateRouteStep(1, 'completed'); // 确保AI分析处理完成
              flowPanel.logRouteStatus('AI分析已完成');
            }

            if (route1Steps[2]?.status !== 'completed') {
              if (route1Steps[2]?.status === 'active') {
                // 如果已经激活但未完成
                flowPanel.updateRouteStep(2, 'completed');
                flowPanel.logRouteStatus('报告生成已完成');
              } else {
                // 如果尚未激活
                flowPanel.updateRouteStep(2, 'active');
                flowPanel.logRouteStatus('报告生成中...');

                // 短暂延迟后完成
                const reportTimeoutId = setTimeout(() => {
                  flowPanel.updateRouteStep(2, 'completed');
                  flowPanel.logRouteStatus('报告生成已完成');
                }, 500);

                // 记录超时ID
                if (!window._flowTimeoutIds) {
                  window._flowTimeoutIds = [];
                }
                window._flowTimeoutIds.push(reportTimeoutId);
              }
            }
          } else if (selectedRouteForThisMessage === 'route2') {
            console.log('执行路线2完成逻辑');
            // 路线2：检查当前状态并完成剩余步骤
            const route2Steps = flowPanel.route2Steps.value || [];
            const hasToolCalls =
              assistantMessage.tool_calls && Object.keys(assistantMessage.tool_calls).length > 0;

            // 获取所有已调用的工具名称
            const toolNames = hasToolCalls
              ? Object.values(assistantMessage.tool_calls || {})
                  .map((call) => (call as any).name)
                  .filter((name) => !!name)
              : [];

            console.log('对话完成时的工具调用:', toolNames);

            // 确保AI分析步骤完成
            if (route2Steps[1]?.status !== 'completed') {
              flowPanel.updateRouteStep(1, 'completed');
              flowPanel.logRouteStatus('AI分析已完成');
            }

            // 确保判断执行工具步骤完成
            if (route2Steps[2]?.status !== 'completed') {
              flowPanel.updateRouteStep(2, 'completed');
              flowPanel.logRouteStatus(hasToolCalls ? '判断需要执行工具' : '判断不需要执行工具');
            }

            // 根据是否有工具调用处理后续步骤
            if (hasToolCalls) {
              // 有工具调用的情况
              if (route2Steps[3]?.status !== 'completed') {
                // 设置工具名称（包含所有工具）
                if (route2Steps[3]) {
                  route2Steps[3].toolName = toolNames.join(', ');

                  // 检查是否是循环调用的多个工具
                  if (toolNames.length > 1) {
                    // 如果有循环节点，设置最后一个工具名
                    if (route2Steps[4]?.nextLoop?.[0]) {
                      const lastTool = toolNames[toolNames.length - 1];
                      route2Steps[4].nextLoop[0].toolName = lastTool;
                      route2Steps[4].nextLoop[0].description = `执行相应的数据处理工具（循环）：${lastTool}`;
                    }
                  }
                }

                flowPanel.updateRouteStep(3, 'completed');
                flowPanel.logRouteStatus(`工具 ${toolNames.join(', ')} 执行已完成`);
              }

              // 确保循环判断步骤完成
              if (route2Steps[4]?.status !== 'completed') {
                if (route2Steps[4]?.status === 'active') {
                  flowPanel.updateRouteStep(4, 'completed');
                  flowPanel.logRouteStatus('全部工具处理完成，不需要循环');
                } else {
                  flowPanel.updateRouteStep(4, 'active');
                  const finalToolTimeoutId = setTimeout(() => {
                    flowPanel.updateRouteStep(4, 'completed');
                    flowPanel.logRouteStatus('全部工具处理完成，不需要循环');
                  }, 500);

                  // 记录超时ID
                  if (!window._flowTimeoutIds) {
                    window._flowTimeoutIds = [];
                  }
                  window._flowTimeoutIds.push(finalToolTimeoutId);
                }
              }
            } else {
              // 没有工具调用的情况，直接完成所有步骤
              flowPanel.updateRouteStep(4, 'completed');
              flowPanel.logRouteStatus('对话完成，无需工具调用');
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
            // 路线1错误处理
            const route1Steps = flowPanel.route1Steps.value || [];

            // 如果当前在AI分析阶段出错
            if (route1Steps[1]?.status === 'active') {
              flowPanel.updateRouteStep(1, 'completed'); // 标记AI分析完成（虽然有错误）
              flowPanel.logRouteStatus('AI分析阶段出错，处理中断');

              // 标记报告生成完成（虽然可能未实际生成）
              flowPanel.updateRouteStep(2, 'completed');
            } else if (route1Steps[2]?.status === 'active') {
              // 如果在报告生成阶段出错
              flowPanel.updateRouteStep(2, 'completed');
              flowPanel.logRouteStatus('报告生成阶段出错，处理中断');
            }
          } else if (selectedRouteForThisMessage === 'route2') {
            // 路线2错误处理
            const route2Steps = flowPanel.route2Steps.value || [];

            // 检查当前处于哪个阶段
            if (route2Steps[1]?.status === 'active') {
              // AI分析阶段出错
              flowPanel.updateRouteStep(1, 'completed');
              flowPanel.logRouteStatus('AI分析阶段出错，处理中断');

              // 标记后续步骤完成
              flowPanel.updateRouteStep(2, 'completed');
              flowPanel.updateRouteStep(4, 'completed');
            } else if (route2Steps[2]?.status === 'active') {
              // 判断执行工具阶段出错
              flowPanel.updateRouteStep(2, 'completed');
              flowPanel.logRouteStatus('判断工具执行阶段出错，处理中断');

              // 标记后续步骤完成
              flowPanel.updateRouteStep(4, 'completed');
            } else if (route2Steps[3]?.status === 'active') {
              // 工具执行阶段出错
              flowPanel.updateRouteStep(3, 'completed');
              flowPanel.logRouteStatus('工具执行阶段出错，处理中断');

              // 标记循环判断完成
              flowPanel.updateRouteStep(4, 'completed');
            } else if (route2Steps[4]?.status === 'active') {
              // 循环判断阶段出错
              flowPanel.updateRouteStep(4, 'completed');
              flowPanel.logRouteStatus('循环判断阶段出错，处理中断');
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
