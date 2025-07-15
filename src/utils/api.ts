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
  column: string;
  type: string;
}

export interface CleaningAction {
  type: string;
  column?: string;
  parameters?: any;
}

export interface ApiResponse {
  file_info: {
    file_id: string;
    original_filename: string;
    user_filename: string;
    description: string;
    upload_time: string;
    file_size: number;
  };
  quality_check: DataQualityReport;
  cleaning_suggestions: CleaningSuggestion[];
  status: string;
}

export const cleaningAPI = {
  // 检查文件数据质量
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

  // 获取清洗建议
  getCleaningSuggestions: async (file: File): Promise<CleaningSuggestion[]> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/clean/suggestions', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 应用清洗动作
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

  // 获取详细的质量报告
  getQualityReport: async (file: File): Promise<DataQualityReport> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/clean/quality-report', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};
