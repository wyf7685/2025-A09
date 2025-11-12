import router from '@/router';
import api from '@/utils/api';
import { persistConfig } from '@/utils/tools';
import { defineStore } from 'pinia';
import { computed } from 'vue';

export const useLoginStore = defineStore('login', () => {
  const token = persistConfig('authToken', '');
  const isLoggedIn = computed(() => token.value !== '');

  const login = async (username: string, password: string) => {
    try {
      const response = await api.post('/auth/login', { username, password });
      token.value = response.data.access_token;
    } catch (error) {
      console.error('登录失败: ', error);
      throw new Error('无效的用户名或密码');
    }
  };

  const logout = () => {
    token.value = '';
    router.push({ path: '/' });
  };

  const getAuthorization = () => `Bearer ${token.value}`;
  const getAuthHeaders = () => ({ Authorization: getAuthorization() });

  const verifyToken = async () => {
    try {
      const response = await api.post<{
        valid: boolean;
        user_id: string;
        username: string;
        message: string;
      }>('/auth/verify', {}, {
        headers: getAuthHeaders(),
      });
      return response.data.valid;
    } catch {
      console.error('Token 验证失败');
      return false;
    }
  };

  const checkLoggedIn = async () => {
    if (isLoggedIn.value) {
      const isValid = await verifyToken();
      if (!isValid)
        logout();
    }
  };

  // 每分钟验证一次Token
  setInterval(() => checkLoggedIn(), 60 * 1000);

  return {
    isLoggedIn,
    login,
    logout,
    getAuthorization,
    getAuthHeaders,
    checkLoggedIn,
  };
});
