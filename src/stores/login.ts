import api from '@/utils/api';
import { persistConfig } from '@/utils/tools';
import { defineStore } from 'pinia';
import { computed } from 'vue';

export const useLoginStore = defineStore('login', () => {
  const token = persistConfig('auth-token', '');

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
  };

  const getAuthorization = () => `Bearer ${token.value}`;
  const getAuthHeaders = () => ({ Authorization: getAuthorization() });

  return {
    isLoggedIn: computed(() => token.value !== ''),
    login,
    logout,
    getAuthorization,
    getAuthHeaders,
  };
});
