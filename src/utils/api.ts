import axios from 'axios';
import { ElMessage } from 'element-plus';

export const API_BASE_URL = 'http://127.0.0.1:8081/api';

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 在这里可以添加 token 等认证信息
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

export const checkHealth = async (): Promise<{ status: string }> => {
  const response = await api.get('/health');
  return response.data;
};

// 数据清洗相关 API
export interface DataQualityReport {
  is_valid: boolean;
  quality_score: number;
  total_rows?: number;
  total_columns?: number;
  issues: Array<{
    type: string;
    column?: string;
    count?: number;
    description: string;
  }>;
  data_info: {
    rows: number;
    columns: number;
    column_names: string[];
    data_types: {
      [column: string]: string;
    };
    missing_values_total: number;
    file_size: number;
  };
}

export interface CleaningSuggestion {
  title: string;
  description: string;
  options: Array<{
    method: string;
    description: string;
  }>;
  severity: string;
  priority?: string;
  impact?: string;
  reason?: string;
  column: string;
  type: string;
}

export interface CleaningAction {
  type: string;
  column?: string;
  parameters?: any;
}

export interface ApiResponse {
  file_info?: {
    file_id: string;
    original_filename: string;
    user_filename: string;
    description: string;
    upload_time: string;
    file_size: number;
  };
  quality_check?: DataQualityReport;
  quality_report?: DataQualityReport;
  cleaning_suggestions?: CleaningSuggestion[];
  field_mappings?: Record<string, string>;
  status: string;
  success?: boolean;
  error?: string;
  summary?: string;
  quality_score?: number;
  field_mappings_applied?: boolean;
  cleaned_file_path?: string;
  data_uploaded?: boolean;
  upload_result?: any;
}

export const cleaningAPI = {
  // 使用智能Agent分析数据质量并生成清洗建议
  analyzeDataQuality: async (
    file: File,
    userRequirements?: string,
    modelName?: string
  ): Promise<ApiResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (userRequirements) {
      formData.append('user_requirements', userRequirements);
    }
    if (modelName) {
      formData.append('model_name', modelName);
    }
    const response = await api.post('/clean/analyze', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 执行用户选择的清洗操作
  executeCleaning: async (
    file: File,
    selectedSuggestions: CleaningSuggestion[],
    fieldMappings?: Record<string, string>,
    userRequirements?: string,
    modelName?: string
  ): Promise<{
    success: boolean;
    file_info: any;
    cleaning_summary: any;
    applied_operations: any[];
    final_columns: string[];
    field_mappings_applied: Record<string, string>;
    cleaned_data_info: any;
    cleaned_file_path: string;
    error?: string;
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const cleaningData = {
      selected_suggestions: selectedSuggestions,
      field_mappings: fieldMappings || {},
      user_requirements: userRequirements,
      model_name: modelName
    };
    
    formData.append('cleaning_data', JSON.stringify(cleaningData));
    
    const response = await api.post('/clean/execute-cleaning', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 完整的分析和清洗流程
  analyzeAndClean: async (
    file: File,
    selectedSuggestions: CleaningSuggestion[],
    fieldMappings?: Record<string, string>,
    userRequirements?: string,
    modelName?: string
  ): Promise<{
    success: boolean;
    file_info: any;
    analysis_result: any;
    cleaning_result: any;
    field_mappings: Record<string, string>;
    applied_operations: any[];
    summary: any;
    cleaned_file_path?: string;
    cleaned_data_info?: any;
    error?: string;
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const cleaningData = {
      selected_suggestions: selectedSuggestions,
      field_mappings: fieldMappings || {},
      user_requirements: userRequirements,
      model_name: modelName
    };
    
    formData.append('cleaning_data', JSON.stringify(cleaningData));
    
    const response = await api.post('/clean/analyze-and-clean', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 检查文件数据质量（保持向后兼容）
  checkDataQuality: async (file: File): Promise<ApiResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/clean/check', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 获取清洗建议（支持用户自定义要求）
  getCleaningSuggestions: async (
    file: File,
    userRequirements?: string
  ): Promise<CleaningSuggestion[]> => {
    const formData = new FormData();
    formData.append('file', file);
    if (userRequirements) {
      formData.append('user_requirements', userRequirements);
    }
    const response = await api.post('/clean/suggestions', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 应用清洗动作（保持向后兼容）
  applyCleaningActions: async (
    file: File,
    actions: CleaningAction[],
  ): Promise<{ success: boolean; message: string; cleaned_file_path?: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('actions', JSON.stringify(actions));
    const response = await api.post('/clean/apply-cleaning', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 获取详细的质量报告（支持用户自定义要求）
  getQualityReport: async (
    file: File,
    userRequirements?: string
  ): Promise<DataQualityReport> => {
    const formData = new FormData();
    formData.append('file', file);
    if (userRequirements) {
      formData.append('user_requirements', userRequirements);
    }
    const response = await api.post('/clean/quality-report', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 获取字段映射（LLM猜测字段名）
  getFieldMapping: async (
    file: File,
    userRequirements?: string,
    modelName?: string
  ): Promise<{
    field_mappings: Record<string, string>;
    summary: string;
    status: string;
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    if (userRequirements) {
      formData.append('user_requirements', userRequirements);
    }
    if (modelName) {
      formData.append('model_name', modelName);
    }
    const response = await api.post('/clean/field-mapping', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 健康检查
  healthCheck: async (): Promise<{
    status: string;
    service: string;
    agent_status: string;
    timestamp: string;
    version: string;
  }> => {
    const response = await api.get('/clean/health');
    return response.data;
  },

  // 保存字段映射到数据源
  saveFieldMappings: async (sourceId: string, fieldMappings: Record<string, string>): Promise<ApiResponse> => {
    const response = await api.post('/clean/save-field-mappings', {
      source_id: sourceId,
      field_mappings: fieldMappings
    });
    return response.data;
  },

  // 获取数据源的字段映射
  getFieldMappings: async (sourceId: string): Promise<ApiResponse> => {
    const response = await api.get(`/clean/field-mappings/${sourceId}`);
    return response.data;
  },
};

// 数据源管理相关 API
export interface DataSourceMetadata {
  id: string;
  name: string;
  source_type: string;
  created_at: string;
  description?: string;
  row_count?: number;
  column_count?: number;
  columns?: string[];
}

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
    cleanedFilePath?: string,
    fieldMappings?: Record<string, string>,
    isCleaned?: boolean
  ): Promise<UploadDataSourceResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    
    if (sourceName) {
      formData.append('source_name', sourceName);
    }
    if (description) {
      formData.append('description', description);
    }
    if (cleanedFilePath) {
      formData.append('cleaned_file_path', cleanedFilePath);
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
    file: File,
    sourceName: string,
    description?: string,
    fieldMappings?: Record<string, string>,
    cleaningSummary?: string
  ): Promise<UploadDataSourceResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_name', sourceName);
    
    if (description) {
      formData.append('description', description);
    }
    if (fieldMappings) {
      formData.append('field_mappings', JSON.stringify(fieldMappings));
    }
    if (cleaningSummary) {
      formData.append('cleaning_summary', cleaningSummary);
    }
    
    const response = await api.post('/datasources/upload-cleaned', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
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
    updates: { name?: string; description?: string }
  ): Promise<DataSourceMetadata> => {
    const response = await api.put(`/datasources/${sourceId}`, updates);
    return response.data;
  },

  // 删除数据源
  deleteDataSource: async (sourceId: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/datasources/${sourceId}`);
    return response.data;
  },

  // 获取数据源数据
  getDataSourceData: async (
    sourceId: string,
    limit: number = 100,
    skip: number = 0
  ): Promise<{
    data: any[];
    total: number;
    skip: number;
    limit: number;
  }> => {
    const response = await api.get(`/datasources/${sourceId}/data`, {
      params: { limit, skip }
    });
    return response.data;
  },
};

// 报告生成API
export const reportAPI = {
  // 获取报告模板列表
  getTemplates: async () => {
    try {
      const response = await api.get('/chat/templates');
      return response.data;
    } catch (error) {
      console.error('获取模板列表失败:', error);
      throw error;
    }
  },

  // 上传自定义模板
  uploadTemplate: async (
    templateName: string,
    templateDescription: string,
    templateFile: File
  ) => {
    try {
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
    } catch (error) {
      console.error('上传模板失败:', error);
      throw error;
    }
  },

  // 删除模板
  deleteTemplate: async (templateId: string) => {
    try {
      const response = await api.delete(`/chat/templates/${templateId}`);
      return response.data;
    } catch (error) {
      console.error('删除模板失败:', error);
      throw error;
    }
  },

  // 生成报告（基于现有的summary功能）
  generateReport: async (
    sessionId: string,
    templateId?: string,
    modelId?: string
  ) => {
    try {
      const response = await api.post('/chat/generate-report', {
        session_id: sessionId,
        template_id: templateId,
        model_id: modelId,
      });
      return response.data;
    } catch (error) {
      console.error('生成报告失败:', error);
      throw error;
    }
  },

  // 获取简单的summary（使用现有接口）
  getSummary: async (sessionId: string, modelId?: string) => {
    try {
      const response = await api.post('/chat/summary', {
        session_id: sessionId,
        model_id: modelId,
      });
      return response.data;
    } catch (error) {
      console.error('获取总结失败:', error);
      throw error;
    }
  },

  // 下载报告为Markdown文件
  downloadReport: (content: string, filename: string = '分析报告.md'): void => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};
