import type { DataSourceMetadata, DremioSource } from '@/types';
import api from '@/utils/api';
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useDataSourceStore = defineStore('dataSource', () => {
  type SourceID = string;
  const dataSources = ref<Record<SourceID, DataSourceMetadata | null>>({});

  const getDataSource = async (sourceId: SourceID) => {
    if (dataSources.value[sourceId]) {
      return dataSources.value[sourceId];
    }
    try {
      const response = await api.get<DataSourceMetadata>(`/datasources/${sourceId}`);
      dataSources.value[sourceId] = response.data;
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch data source ${sourceId}:`, error);
      throw error;
    }
  };

  const listDataSources = async () => {
    try {
      const response = await api.get<SourceID[]>('/datasources');
      for (const id of response.data) {
        if (!dataSources.value[id]) {
          try {
            const source = await getDataSource(id);
            dataSources.value[id] = source;
          } catch (error) {
            console.error(`Failed to fetch data source ${id}:`, error);
          }
        }
      }
      return Object.entries(dataSources.value)
        .filter(([_, ds]) => ds !== null)
        .map(([id, ds]) => ({ ...ds, source_id: id })) as (DataSourceMetadata & {
        source_id: SourceID;
      })[];
    } catch (error) {
      console.error('Failed to fetch data sources:', error);
      throw error;
    }
  };

  const registerDremioSource = async (source: DremioSource) => {
    try {
      const response = await api.post<{
        source_id: SourceID;
        metadata: DataSourceMetadata;
      }>('/datasources/register', { source });
      dataSources.value[response.data.source_id] = response.data.metadata;
      return response.data;
    } catch (error) {
      console.error('Failed to register data source:', error);
      throw error;
    }
  };

  const uploadCsvSource = async (file: File, sourceName?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (sourceName) {
      formData.append('source_name', sourceName);
    }

    try {
      const response = await api.post<{
        source_id: SourceID;
        metadata: DataSourceMetadata;
      }>('/datasources/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      dataSources.value[response.data.source_id] = response.data.metadata;
      return response.data;
    } catch (error) {
      console.error('Failed to upload CSV source:', error);
      throw error;
    }
  };

  const getSourceData = async (sourceId: SourceID, skip: number = 0, limit: number = 100) => {
    try {
      const response = await api.get<{
        data: Record<SourceID, any>[];
        total: number;
        skip: number;
        limit: number;
      }>(`/datasources/${sourceId}/data`, {
        params: { skip, limit },
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch data for source ${sourceId}:`, error);
      throw error;
    }
  };

  const deleteDataSource = async (sourceId: SourceID) => {
    try {
      await api.delete(`/datasources/${sourceId}`);
      delete dataSources.value[sourceId];
    } catch (error) {
      console.error(`Failed to delete data source ${sourceId}:`, error);
      throw error;
    }
  };

  const getSourceId = (metadata: DataSourceMetadata) => {
    for (const [id, ds] of Object.entries(dataSources.value)) {
      if (ds && ds.id === metadata.id) {
        return id;
      }
    }
  };

  return {
    dataSources,
    getDataSource,
    listDataSources,
    registerDremioSource,
    uploadCsvSource,
    getSourceData,
    deleteDataSource,
    getSourceId,
  };
});
