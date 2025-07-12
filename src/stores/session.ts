import type { ChatEntry, Session, SessionListItem, ToolCallArtifact } from '@/types';
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import api, { API_BASE_URL } from '../utils/api';

export const useSessionStore = defineStore('session', () => {
  const currentSession = ref<Session | null>(null);
  const sessions = ref<SessionListItem[]>([]);
  const chatHistory = ref<ChatEntry[]>([]);

  // 会话管理
  const createSession = async (dataset_id: string) => {
    const response = await api.post<Session>('/sessions', { dataset_id });
    await listSessions();
    return response.data;
  };

  const setCurrentSession = (session: Session) => {
    currentSession.value = session;
  };

  const setCurrentSessionById = async (sessionId: string) => {
    setCurrentSession(await getSession(sessionId));
    await listSessions();
  };

  // 更新会话名称
  const updateSessionName = async (sessionId: string, name: string | null) => {
    // 更新本地会话列表中的会话名称
    const sessionIndex = sessions.value.findIndex(s => s.id === sessionId);
    if (sessionIndex !== -1) {
      sessions.value[sessionIndex].name = name;
    }
    
    // 如果当前会话是目标会话，也更新当前会话
    if (currentSession.value?.id === sessionId) {
      currentSession.value.name = name;
    }
  };

  const listSessions = async () => {
    const response = await api.get<SessionListItem[]>('/sessions');
    sessions.value = response.data;
    return response.data;
  };

  const getSession = async (sessionId: string): Promise<Session> => {
    const response = await api.get<Session>(`/sessions/${sessionId}`);
    return response.data;
  };

  const deleteSession = async (sessionId: string): Promise<void> => {
    await api.delete(`/sessions/${sessionId}`);
    if (currentSession.value?.id === sessionId) {
      currentSession.value = null;
    }
    await listSessions();
  };

  // 流式对话分析
  const sendStreamChatMessage = async (
    message: string,
    onMessage: (content: string) => void,
    onToolCall: (id: string, name: string, args: any) => void,
    onToolResult: (id: string, result: any, artifact: ToolCallArtifact | null) => void,
    onToolError: (id: string, error: string) => void,
    onDone: () => void,
    onError: (error: string) => void,
  ): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          session_id: currentSession.value!.id,
          dataset_id: currentSession.value!.dataset_id,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body reader could not be created');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        // 解码并添加到缓冲区
        buffer += decoder.decode(value, { stream: true });

        // 处理每一行
        const lines = buffer.split('\n');
        // 除了最后一行外，其余行都是完整的
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);

            // 根据后端返回的事件类型处理不同的响应
            if (data.type === 'llm_token') {
              onMessage(data.content);
            } else if (data.type === 'tool_call') {
              onToolCall(data.id, data.name, data.args);
            } else if (data.type === 'tool_result') {
              onToolResult(data.id, data.result, data.artifact || null);
            } else if (data.type === 'tool_error') {
              onToolError(data.id, data.error);
            } else if (data.type === 'done') {
              onDone();
            } else if (data.error) {
              onError(data.error);
            }
          } catch (e) {
            console.error('Failed to parse SSE message:', line, e);
          }
        }
      }
    } catch (error) {
      console.error('Stream chat error:', error);
      onError(error instanceof Error ? error.message : String(error));
    }
  };

  return {
    currentSession: computed(() => currentSession.value),
    sessions,
    chatHistory,
    createSession,
    setCurrentSession,
    setCurrentSessionById,
    listSessions,
    getSession,
    deleteSession,
    sendStreamChatMessage,
    updateSessionName,
  };
});
