import type {
  AnalysisReport,
  AnalysisResult,
  ChatEntry,
  Dataset,
  Model,
  Session,
  UploadResult,
} from '@/types';
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import api from '../utils/api';

export const useAppStore = defineStore('app', () => {
  // 状态
  const currentSessionId = ref<string>('');
  const currentDataset = ref<Dataset | null>(null);
  const loading = ref<boolean>(false);
  const chatHistory = ref<ChatEntry[]>([]);
  const analysisResults = ref<AnalysisResult[]>([]);

  // 设置当前会话
  const setCurrentSession = (sessionId: string): void => {
    currentSessionId.value = sessionId;
  };

  // 设置当前数据集
  const setCurrentDataset = (dataset: Dataset): void => {
    currentDataset.value = dataset;
  };

  // 健康检查
  const checkHealth = async (): Promise<{ status: string }> => {
    const response = await api.get('/health');
    return response.data;
  };

  // 会话管理
  const createSession = async (): Promise<{ session_id: string }> => {
    const response = await api.post('/sessions');
    return response.data;
  };

  const getSessions = async (): Promise<Session[]> => {
    const response = await api.get('/sessions');
    return response.data;
  };

  const getSession = async (sessionId: string): Promise<Session> => {
    const response = await api.get(`/sessions/${sessionId}`);
    return response.data;
  };

  // 文件上传
  const uploadFile = async (file: File, sessionId: string | null = null): Promise<UploadResult> => {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) {
      formData.append('session_id', sessionId);
    }

    loading.value = true;
    try {
      const response = await api.post('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } finally {
      loading.value = false;
    }
  };

  // Dremio 数据源
  const getDremioSources = async (): Promise<{ sources: string[] }> => {
    const response = await api.get('/dremio/sources');
    return response.data;
  };

  const loadDremioData = async (
    sourceName: string,
    sessionId: string,
  ): Promise<{ dataset_id: string }> => {
    loading.value = true;
    try {
      const response = await api.post('/dremio/load', {
        source_name: sourceName,
        session_id: sessionId,
      });
      return response.data;
    } finally {
      loading.value = false;
    }
  };

  // 对话分析
  const sendChatMessage = async (
    message: string,
    sessionId: string,
    datasetId: string | null = null,
  ): Promise<{ chat_entry: ChatEntry; analysis?: any }> => {
    loading.value = true;
    try {
      const response = await api.post<{
        chat_entry: ChatEntry;
        analysis?: any;
      }>('/chat', {
        message,
        session_id: sessionId,
        dataset_id: datasetId,
      });

      // 更新聊天历史
      if (response.data.chat_entry) {
        chatHistory.value.push(response.data.chat_entry);
      }

      return response.data;
    } finally {
      loading.value = false;
    }
  };

  // 流式对话分析
  const sendStreamChatMessage = async (
    message: string,
    sessionId: string,
    datasetId: string | null = null,
    onChunk: (chunk: string) => void,
    onResults: (results: any[]) => void,
    onDone: () => void,
    onError: (error: string) => void,
  ): Promise<void> => {
    loading.value = true;

    try {
      const response = await fetch(`/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          session_id: sessionId,
          dataset_id: datasetId,
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

            // 处理不同类型的响应
            if (data.type === 'chunk') {
              onChunk(data.content);
            } else if (data.type === 'results') {
              onResults(data.results);
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
      loading.value = false;
    }
  };

  // 自动分析
  const runGeneralAnalysis = async (sessionId: string): Promise<AnalysisReport> => {
    loading.value = true;
    try {
      const response = await api.post('/analysis/general', {
        session_id: sessionId,
      });

      // 更新分析结果
      if (response.data.report) {
        analysisResults.value.push(response.data);
      }

      return response.data;
    } finally {
      loading.value = false;
    }
  };

  // 模型管理
  const getModels = async (sessionId: string): Promise<Model[]> => {
    const response = await api.get('/models', {
      params: { session_id: sessionId },
    });
    return response.data;
  };

  const deleteModel = async (modelId: string): Promise<{ success: boolean }> => {
    const response = await api.delete(`/models/${modelId}`);
    return response.data;
  };

  // 数据集管理
  const getDatasets = async (sessionId: string | null = null): Promise<Dataset[]> => {
    const params = sessionId ? { session_id: sessionId } : {};
    const response = await api.get('/datasets', { params });
    return response.data;
  };

  const getDatasetPreview = async (
    datasetId: string,
    limit: number = 10,
  ): Promise<{ columns: string[]; data: any[] }> => {
    const response = await api.get(`/datasets/${datasetId}/preview`, {
      params: { limit },
    });
    return response.data;
  };

  // 导出报告
  const exportReport = async (format: 'markdown' | 'pdf' | 'html' = 'markdown'): Promise<Blob> => {
    const sessionId = currentSessionId.value;
    if (!sessionId) {
      throw new Error('No current session');
    }

    const response = await api.post(
      '/export/report',
      {
        session_id: sessionId,
        format,
      },
      {
        responseType: 'blob',
      },
    );

    return response.data;
  };

  // 获取当前会话信息
  const currentSession = computed<Session>(() => {
    return {
      id: currentSessionId.value,
      current_dataset: currentDataset.value?.id,
      chat_history: chatHistory.value,
      analysis_results: analysisResults.value,
    };
  });
  return {
    // 状态
    currentSessionId,
    currentDataset,
    loading,
    chatHistory,
    analysisResults,

    // 计算属性
    currentSession,

    // 方法
    setCurrentSession,
    setCurrentDataset,
    checkHealth,
    createSession,
    getSessions,
    getSession,
    uploadFile,
    getDremioSources,
    loadDremioData,
    sendChatMessage,
    sendStreamChatMessage,
    runGeneralAnalysis,
    getModels,
    deleteModel,
    getDatasets,
    getDatasetPreview,
    exportReport,
  };
});
