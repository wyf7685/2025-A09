import axios from 'axios';
import { ElMessage } from 'element-plus';

export const API_BASE_URL = 'http://127.0.0.1:8000/api';

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
