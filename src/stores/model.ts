import type { Model } from '@/types';
import api from '@/utils/api';
import { defineStore } from 'pinia';

export const useModelStore = defineStore('model', () => {
  // TODO: Implement model management

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

  return {
    getModels,
    deleteModel,
  };
});
