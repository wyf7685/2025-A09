import type { ChatEntry, MLModel, Session, SessionListItem, ToolCallArtifact } from '@/types';
import { ElMessage } from 'element-plus';
import { defineStore } from 'pinia';
import { computed, reactive, ref } from 'vue';
import api, { API_BASE_URL } from '../utils/api';
import { useLoginStore } from './login';

export const useSessionStore = defineStore('session', () => {
  const loginStore = useLoginStore();

  const currentSessionReactive = reactive<{ session: Session | null; }>({ session: null });
  const currentSession = computed({
    get: () => currentSessionReactive.session,
    set: (value: Session | null) => {
      currentSessionReactive.session = value;
    },
  });
  const currentSessionName = computed(() =>
    currentSession.value
      ? currentSession.value.name || `会话 ${currentSession.value.id.substring(0, 8)}`
      : '',
  );
  const sessions = ref<SessionListItem[]>([]);
  const chatHistory = ref<ChatEntry[]>([]);
  const isDeleting = ref<Record<string, boolean>>({});

  // 会话管理
  const createSession = async (dataset_ids: string[]) => {
    const response = await api.post<Session>('/sessions', { dataset_ids });
    await listSessions();
    return response.data;
  };

  const setCurrentSession = (session: Session) => {
    currentSession.value = session;
  };

  const setCurrentSessionById = async (sessionId: string): Promise<void> => {
    try {
      setCurrentSession(await getSession(sessionId));
      await listSessions();
    } catch (error) {
      console.error('设置当前会话失败:', error);
      ElMessage.error('设置当前会话失败，请刷新页面重试');
    }
  };

  // 更新会话名称
  const updateSessionName = async (sessionId: string, name: string | null): Promise<void> => {
    if (!name) return;

    try {
      // 调用后端API更新会话名称
      await api.put<Session>(`/sessions/${sessionId}`, { name });

      // 更新本地会话列表中的会话名称
      const sessionIndex = sessions.value.findIndex((s) => s.id === sessionId);
      if (sessionIndex !== -1) {
        sessions.value[sessionIndex].name = name;
      }

      // 如果当前会话是目标会话，也更新当前会话
      if (currentSession.value?.id === sessionId) {
        currentSession.value.name = name;
      }
    } catch (error) {
      console.error('更新会话名称失败:', error);
      throw error;
    }
  };

  const refreshSessionName = async (sessionId: string): Promise<string> => {
    try {
      const response = await api.get<{ name: string | null; }>(`/sessions/${sessionId}/name`);
      const name = response.data.name || `会话 ${sessionId.substring(0, 8)}`;

      // 更新本地会话列表中的会话名称
      const sessionIndex = sessions.value.findIndex((s) => s.id === sessionId);
      if (sessionIndex !== -1) {
        sessions.value[sessionIndex].name = name;
      }

      // 如果当前会话是目标会话，也更新当前会话
      if (currentSession.value?.id === sessionId) {
        currentSession.value.name = name;
      }

      return name;
    } catch (error) {
      console.error(`获取会话 ${sessionId} 名称失败:`, error);
      throw error;
    }
  };

  const listSessions = async () => {
    try {
      const response = await api.get<SessionListItem[]>('/sessions');
      sessions.value = response.data;
      return response.data;
    } catch (error) {
      console.error('获取会话列表失败:', error);
      ElMessage.error('获取会话列表失败');
      throw error;
    }
  };

  const getSession = async (sessionId: string): Promise<Session> => {
    try {
      const response = await api.get<Session>(`/sessions/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error(`获取会话 ${sessionId} 失败:`, error);
      throw error;
    }
  };

  const deleteSession = async (sessionId: string, retryCount = 0): Promise<void> => {
    // 防止重复删除
    if (isDeleting.value[sessionId]) {
      return;
    }

    isDeleting.value[sessionId] = true;

    try {
      // 先更新本地状态，提供更好的用户体验
      if (currentSession.value?.id === sessionId) {
        currentSession.value = null;
      }

      // 从本地列表中移除
      const sessionIndex = sessions.value.findIndex((s) => s.id === sessionId);
      if (sessionIndex !== -1) {
        sessions.value.splice(sessionIndex, 1);
      }

      // 调用后端API删除
      await api.delete(`/sessions/${sessionId}`);

      console.log(`会话 ${sessionId} 删除成功`);
    } catch (error) {
      console.error(`删除会话 ${sessionId} 失败:`, error);

      // 最多重试2次
      if (retryCount < 2) {
        console.log(`尝试重新删除会话 ${sessionId}，第 ${retryCount + 1} 次重试`);
        setTimeout(() => {
          isDeleting.value[sessionId] = false;
          deleteSession(sessionId, retryCount + 1);
        }, 1000); // 延迟1秒后重试
        return;
      } else {
        // 重试失败后，重新获取会话列表以恢复正确的状态
        await listSessions();
        throw error;
      }
    } finally {
      isDeleting.value[sessionId] = false;
    }
  };

  // 流式对话分析
  const sendStreamChatMessage = async (
    message: string,
    onMessage: (content: string) => void,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onToolCall: (id: string, name: string, args: any, source: string) => void,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onToolResult: (id: string, result: any, artifact: ToolCallArtifact | null) => void,
    onToolError: (id: string, error: string) => void,
    onDone: () => void,
    onError: (error: string) => void,
    modelId?: string,
  ): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...loginStore.getAuthHeaders(),
        },
        body: JSON.stringify({
          message: message,
          session_id: currentSession.value!.id,
          model_id: modelId || 'gemini-2.0-flash',
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
              onToolCall(data.id, data.human_repr, data.args, data.source);
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
    } finally {
      await refreshSessionName(currentSession.value!.id);
    }
  };

  const summaryChat = async (sessionId: string): Promise<string> => {
    const response = await api.post<{ summary: string; }>('/chat/summary', {
      session_id: sessionId,
    });
    return response.data.summary;
  };

  // 获取会话关联的模型
  const getSessionModels = async (sessionId: string) => {
    try {
      const response = await api.get<MLModel[]>(`/sessions/${sessionId}/models`);
      return response.data;
    } catch (error) {
      console.error(`获取会话 ${sessionId} 的模型失败:`, error);
      throw error;
    }
  };

  // 添加模型到会话
  const addModelsToSession = async (sessionId: string, modelIds: string[]) => {
    try {
      await api.post(`/sessions/${sessionId}/models`, {
        model_ids: modelIds,
      });
    } catch (error) {
      console.error(`向会话 ${sessionId} 添加模型失败:`, error);
      ElMessage.error('添加模型失败');
      throw error;
    }
  };

  // 从会话中移除模型
  const removeModelsFromSession = async (sessionId: string, modelIds: string[]) => {
    try {
      await api.delete(`/sessions/${sessionId}/models`, {
        data: { model_ids: modelIds },
      });
    } catch (error) {
      console.error(`从会话 ${sessionId} 移除模型失败:`, error);
      ElMessage.error('移除模型失败');
      throw error;
    }
  };

  // 更新会话关联的模型
  const updateSessionModels = async (sessionId: string, modelIds: string[]) => {
    try {
      // 先获取当前会话的模型
      const currentModels = await getSessionModels(sessionId);
      const currentModelIds = currentModels.map(model => model.id);

      // 计算要添加和删除的模型ID
      const modelsToAdd = modelIds.filter((id) => !currentModelIds.includes(id));
      const modelsToRemove = currentModelIds.filter((id) => !modelIds.includes(id));

      // 执行添加和移除操作
      if (modelsToAdd.length > 0) {
        await addModelsToSession(sessionId, modelsToAdd);
      }

      if (modelsToRemove.length > 0) {
        await removeModelsFromSession(sessionId, modelsToRemove);
      }
    } catch (error) {
      console.error(`更新会话 ${sessionId} 模型失败:`, error);
      ElMessage.error('更新会话模型失败');
      throw error;
    }
  };

  const updateSessionAgentModelConfig = async (config: {
    default?: string;
    chat?: string;
    create_title?: string;
    summary?: string;
    code_generation?: string;
  }) => {
    if (!currentSession.value) {
      throw new Error('No current session selected');
    }

    try {
      await api.put<void>(`/sessions/${currentSession.value.id}/model_config`, config);

      // 成功更新后端配置后，同步更新前端的 currentSession 状态
      if (currentSession.value.agent_model_config) {
        currentSession.value.agent_model_config = {
          ...currentSession.value.agent_model_config,
          ...config,
        };
      }
    } catch (error) {
      console.error('更新会话模型配置失败:', error);
      ElMessage.error('更新会话模型配置失败');
      throw error;
    }
  };

  return {
    currentSession: computed(() => currentSession.value),
    currentSessionId: computed(() => currentSession.value?.id),
    currentSessionName,
    sessions,
    chatHistory,
    createSession,
    setCurrentSession,
    setCurrentSessionById,
    updateSessionName,
    refreshSessionName,
    listSessions,
    getSession,
    deleteSession,
    sendStreamChatMessage,
    summaryChat,
    isDeleting: computed(() => isDeleting.value),
    // 模型相关
    getSessionModels,
    addModelsToSession,
    removeModelsFromSession,
    updateSessionModels,
    // Agent 模型配置
    updateSessionAgentModelConfig,
  };
});
