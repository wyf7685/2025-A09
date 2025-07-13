import type { Model, ModelsResponse, LLMModel } from '@/types';
import api from '@/utils/api';
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

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
    } catch (error) {
      console.error('Failed to fetch available models:', error);
    }
  };

  // 设置选择的模型
  const setSelectedModel = (model: LLMModel) => {
    selectedModel.value = model;
  };

  return {
    selectedModel: computed(() => selectedModel.value),
    availableModels: computed(() => availableModels.value),
    getModels,
    getAllModels,
    deleteModel,
    fetchAvailableModels,
    setSelectedModel,
  };
});
