import { useLoginStore } from '@/stores/login';
import type {
  AnalyzeDataQualityResponse,
  AnalyzeDataQualitySuccess,
  CleaningSuggestion,
} from '@/types/cleaning';
import type { DataSourceMetadata } from '@/types/dataSources';
import type { ReportTemplate } from '@/types/report';
import axios from 'axios';
import { ElMessage } from 'element-plus';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000, // 60秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

const apiRequiresLogin = (endpoint?: string) => {
  if (!endpoint)
    return true;
  if (endpoint.startsWith('/auth/') || endpoint === '/health')
    return false;
  return true;
};

// 请求拦截器
api.interceptors.request.use(
  async (config) => {
    if (apiRequiresLogin(config.url)) {
      const loginStore = useLoginStore();
      if (loginStore.isLoggedIn) {
        config.headers.Authorization = loginStore.getAuthorization();
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // 统一错误处理
    let errorMessage = '请求失败';

    if (error.response) {
      // 服务器返回的错误
      const { status, data } = error.response;

      switch (status) {
        case 400:
          errorMessage = data.error || '请求参数错误';
          break;
        case 401:
          errorMessage = '未授权访问';
          break;
        case 403:
          errorMessage = '禁止访问';
          break;
        case 404:
          errorMessage = '资源不存在';
          break;
        case 500:
          errorMessage = data.error || '服务器内部错误';
          break;
        case 503:
          errorMessage = data.error || '服务暂时不可用';
          break;
        default:
          errorMessage = data.error || `请求失败 (${status})`;
      }
    } else if (error.request) {
      // 网络错误
      errorMessage = '网络连接失败，请检查网络设置';
    } else {
      // 其他错误
      errorMessage = error.message || '未知错误';
    }

    // 显示错误消息
    ElMessage.error(errorMessage);

    return Promise.reject(error);
  },
);

export default api;

export const checkHealth = async (): Promise<{ status: string; }> => {
  const response = await api.get('/health');
  return response.data;
};

// 数据清洗相关 API
export const cleaningAPI = {
  // 使用智能Agent分析数据质量并生成清洗建议
  analyzeDataQuality: async (
    file: File,
    userRequirements?: string,
    modelId?: string,
  ): Promise<AnalyzeDataQualitySuccess> => {
    const formData = new FormData();
    formData.append('file', file);
    if (userRequirements) {
      formData.append('user_requirements', userRequirements);
    }
    if (modelId) {
      formData.append('model_id', modelId);
    }
    const response = await api.post<AnalyzeDataQualityResponse>('/clean/analyze', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    if (!response.data.success) {
      throw new Error(response.data.error || '数据分析失败');
    }
    return response.data;
  },

  // 执行用户选择的清洗操作
  executeCleaning: async (
    file: File,
    selectedSuggestions: CleaningSuggestion[],
    fieldMappings?: Record<string, string>,
    userRequirements?: string,
    modelName?: string,
  ): Promise<{
    success: boolean;
    cleaned_file_id: string;
    error?: string;
  }> => {
    const formData = new FormData();
    formData.append('file', file);

    const cleaningData = {
      selected_suggestions: selectedSuggestions,
      field_mappings: fieldMappings || {},
      user_requirements: userRequirements,
      model_name: modelName,
    };

    formData.append('cleaning_data', JSON.stringify(cleaningData));

    const response = await api.post('/clean/execute-cleaning', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 获取生成的清洗代码
  getGeneratedCode: async (
    cleanedFileId: string,
  ): Promise<{
    success: boolean;
    file_id?: string;
    generated_code?: string;
    message?: string;
    error?: string;
  }> => {
    const response = await api.get(`/clean/${cleanedFileId}/code`);
    return response.data;
  },
};

// 数据源管理相关 API
export interface UploadDataSourceResponse {
  source_id: string;
  metadata: DataSourceMetadata;
}

export const dataSourceAPI = {
  // 上传文件数据源（支持清洗后的数据）
  uploadFile: async (
    file: File,
    sourceName?: string,
    description?: string,
    cleanedFileId?: string,
    fieldMappings?: Record<string, string>,
    isCleaned?: boolean,
  ): Promise<UploadDataSourceResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    if (sourceName) {
      formData.append('source_name', sourceName);
    }
    if (description) {
      formData.append('description', description);
    }
    if (cleanedFileId) {
      formData.append('cleaned_file_id', cleanedFileId);
    }
    if (fieldMappings) {
      formData.append('field_mappings', JSON.stringify(fieldMappings));
    }
    if (isCleaned !== undefined) {
      formData.append('is_cleaned', isCleaned.toString());
    }

    const response = await api.post('/datasources/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 上传清洗后的数据文件
  uploadCleanedFile: async (
    cleanedFileId: string,
    sourceName: string,
    description?: string,
    fieldMappings?: Record<string, string>,
    cleaningSummary?: string,
  ): Promise<UploadDataSourceResponse> => {
    const response = await api.post('/datasources/upload-cleaned', {
      cleaned_file_id: cleanedFileId,
      source_name: sourceName,
      description,
      field_mappings: fieldMappings,
      cleaning_summary: cleaningSummary,
    });
    return response.data;
  },

  // 获取数据源列表
  listDataSources: async (): Promise<string[]> => {
    const response = await api.get('/datasources');
    return response.data;
  },

  // 获取数据源详情
  getDataSource: async (sourceId: string): Promise<DataSourceMetadata> => {
    const response = await api.get(`/datasources/${sourceId}`);
    return response.data;
  },

  // 更新数据源信息
  updateDataSource: async (
    sourceId: string,
    updates: { name?: string; description?: string; },
  ): Promise<DataSourceMetadata> => {
    const response = await api.put(`/datasources/${sourceId}`, updates);
    return response.data;
  },

  // 删除数据源
  deleteDataSource: async (sourceId: string): Promise<{ success: boolean; message: string; }> => {
    const response = await api.delete(`/datasources/${sourceId}`);
    return response.data;
  },

  // 获取数据源数据
  getDataSourceData: async (
    sourceId: string,
    limit: number = 100,
    skip: number = 0,
  ): Promise<{
    data: unknown[];
    total: number;
    skip: number;
    limit: number;
  }> => {
    const response = await api.get(`/datasources/${sourceId}/data`, {
      params: { limit, skip },
    });
    return response.data;
  },
};

// 报告相关 API
export const reportAPI = {
  getTemplates: async () => {
    const response = await api.get<ReportTemplate[]>('/chat/templates');
    return response.data;
  },

  uploadTemplate: async (templateName: string, templateDescription: string, templateFile: File) => {
    const formData = new FormData();
    formData.append('template_name', templateName);
    formData.append('template_description', templateDescription);
    formData.append('template_file', templateFile);

    const response = await api.post('/chat/templates/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  deleteTemplate: async (templateId: string) => {
    const response = await api.delete(`/chat/templates/${templateId}`);
    return response.data;
  },

  generateReport: async (sessionId: string, templateId?: string, modelId?: string) => {
    const payload: Record<string, string> = { session_id: sessionId };
    if (templateId) payload.template_id = templateId;
    if (modelId) payload.model_id = modelId;
    const response = await api.post('/chat/generate-report', payload);
    return response.data;
  },

  downloadReport: (content: string, filename: string = '分析报告.md'): void => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};
