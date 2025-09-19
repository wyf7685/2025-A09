import type { LLMModel, ModelsResponse } from '@/types';
import api, { API_BASE_URL } from '@/utils/api';
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

export const useModelStore = defineStore('model', () => {
  const selectedModel = ref<LLMModel | null>(null);
  const availableModels = ref<LLMModel[]>([]);

  const getModels = async (sessionId: string): Promise<ModelsResponse> => {
    const response = await api.get('/models', {
      params: { session_id: sessionId },
    });
    return response.data;
  };

  const getAllModels = async (): Promise<ModelsResponse> => {
    const response = await api.get('/models/all');
    return response.data;
  };

  const deleteModel = async (modelId: string): Promise<{ success: boolean }> => {
    const response = await api.delete(`/models/${modelId}`);
    return response.data;
  };

  // 获取可用模型
  const fetchAvailableModels = async () => {
    try {
      const response = await api.get('/models/available');
      availableModels.value = response.data.models;

      // 如果当前选择的模型不在可用模型中，选择第一个可用模型
      if (
        !selectedModel.value ||
        !availableModels.value.some((m) => m.id === selectedModel.value?.id)
      ) {
        selectedModel.value = availableModels.value[0] || null;
      }

      return availableModels.value;
    } catch (error) {
      console.error('Failed to fetch available models:', error);
      return [];
    }
  };

  // 设置选择的模型
  const setSelectedModel = (model: LLMModel) => {
    selectedModel.value = model;
  };

  const submitCustomModel = async (params: {
    name: string;
    provider: string;
    api_url: string;
    api_key: string;
    model_name: string;
  }) => {
    try {
      const response = await api.post<{
        success: true;
        message: string;
        model_id: string;
      }>('/models/custom', params);

      const customModel = {
        id: response.data.model_id,
        name: params.model_name,
        provider: params.provider,
        apiUrl: params.api_url,
        apiKey: params.api_key,
      };
      setCustomModel(customModel);
      setSelectedModel(customModel);

      return customModel;
    } catch (error) {
      console.error('Failed to submit custom model:', error);
      throw error;
    }
  };

  // 删除自定义模型
  const deleteCustomModel = async (modelId: string): Promise<{ success: boolean }> => {
    try {
      const response = await api.delete(`/models/custom/${modelId}`);
      if (response.data.success) {
        // 从本地列表中移除
        const index = availableModels.value.findIndex(m => m.id === modelId);
        if (index !== -1) {
          availableModels.value.splice(index, 1);
        }

        // 如果删除的是当前选中的模型，选择第一个可用模型
        if (selectedModel.value?.id === modelId) {
          selectedModel.value = availableModels.value[0] || null;
        }
      }
      return response.data;
    } catch (error) {
      console.error('Failed to delete custom model:', error);
      throw error;
    }
  };

  // 获取自定义模型详细配置
  const getCustomModel = async (modelId: string) => {
    try {
      const response = await api.get(`/models/custom/${modelId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get custom model:', error);
      throw error;
    }
  };

  // 更新自定义模型
  const updateCustomModel = async (modelId: string, params: {
    name?: string;
    provider?: string;
    api_url?: string;
    api_key?: string;
    model_name?: string;
  }) => {
    try {
      const response = await api.put(`/models/custom/${modelId}`, params);
      if (response.data.success) {
        // 更新本地列表中的模型
        const index = availableModels.value.findIndex(m => m.id === modelId);
        if (index !== -1) {
          availableModels.value[index] = {
            ...availableModels.value[index],
            ...params,
            apiUrl: params.api_url || availableModels.value[index].apiUrl,
            apiKey: params.api_key || availableModels.value[index].apiKey,
          };
        }

        // 如果更新的是当前选中的模型，更新选中状态
        if (selectedModel.value?.id === modelId) {
          selectedModel.value = availableModels.value[index];
        }
      }
      return response.data;
    } catch (error) {
      console.error('Failed to update custom model:', error);
      throw error;
    }
  };

  // 设置自定义模型
  const setCustomModel = (model: LLMModel) => {
    // 将自定义模型添加到可用模型列表中（如果不存在的话）
    const existingIndex = availableModels.value.findIndex((m) => m.id === model.id);
    if (existingIndex === -1) {
      availableModels.value.push(model);
    } else {
      availableModels.value[existingIndex] = model;
    }
  };

  const downloadModel = (modelId: string) => {
    const link = document.createElement('a');
    link.href = `${API_BASE_URL}/models/download/${modelId}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  return {
    selectedModel: computed(() => selectedModel.value),
    availableModels: computed(() => availableModels.value),
    getModels,
    getAllModels,
    deleteModel,
    fetchAvailableModels,
    setSelectedModel,
    setCustomModel,
    submitCustomModel,
    getCustomModel,
    deleteCustomModel,
    updateCustomModel,
    downloadModel,
  };
});
