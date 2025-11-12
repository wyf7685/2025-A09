import { useSessionStore } from '@/stores/session';
import type {
  AssistantChatMessage,
  AssistantChatMessageContent,
  AssistantChatMessageText,
  ChatMessage,
  DataSourceMetadata,
} from '@/types';
import { ElMessage } from 'element-plus';
import { nextTick, reactive, ref } from 'vue';


type MessageExtraState = { loading?: boolean; suggestions?: string[]; };
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

export const useChat = () => {
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
            } as AssistantChatMessageWithSuggestions;

            // 重新提取建议按钮（页面刷新后恢复建议）
            const mergedContent = assistantMessage.content
              .map((c) => (c.type === 'text' ? c.content : ''))
              .join('');

            const suggestions = extractSuggestions(mergedContent);
            if (suggestions.length > 0) {
              assistantMessage.suggestions = suggestions;
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

          nextTick(() => scrollToBottom?.());
        },
        (id, name, args, source) => {
          // 工具调用
          if (!assistantMessage.tool_calls) assistantMessage.tool_calls = {};
          assistantMessage.tool_calls[id] = {
            name,
            args,
            source,
            status: 'running',
          };
          assistantMessage.content.push({ type: 'tool_call', id });


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
          console.log('assistantMessage.tool_calls:', assistantMessage.tool_calls);

          assistantMessage.loading = false;

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

          if (currentSessionId) {
            sessionStore.refreshSessionName(currentSessionId);
          }
          nextTick(() => scrollToBottom?.());
        },
        (error) => {
          // 错误处理
          console.error('对话处理错误:', error);
          ElMessage.error(`处理消息时出错: ${error}`);
          pushText(`\n\n处理出错: ${error}`);

          nextTick(() => scrollToBottom?.());
        },
      );

      assistantMessage.loading = false;
    } catch (error) {
      console.error('发送消息失败:', error);

      // 添加错误消息
      messages.value.push({
        type: 'assistant',
        content: [{ type: 'text', content: '抱歉，处理您的请求时出现了错误。请稍后重试。' }],
        timestamp: new Date().toISOString(),
      });

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
