import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '../utils/api';
import type { ChatEntry, Dataset, AnalysisResult, Session, Model, AnalysisReport, UploadResult } from '@/types';

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
  const uploadFile = async (
    file: File,
    sessionId: string | null = null,
  ): Promise<UploadResult> => {
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
    runGeneralAnalysis,
    getModels,
    deleteModel,
    getDatasets,
    getDatasetPreview,
    exportReport,
  };
});
