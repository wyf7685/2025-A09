import { defineStore } from 'pinia';
import { ref } from 'vue';
import { sleep } from '@/utils/tools';

export const useLoginStore = defineStore('login', () => {
  const isLoggedIn = ref(localStorage.getItem('isLoggedIn') === 'true');

  const login = async (username: string, password: string) => {
    await sleep(1000); // Simulate network delay
    if (username === 'dataforge' && password === 'operator@dataforge.chat') {
      isLoggedIn.value = true;
      localStorage.setItem('isLoggedIn', 'true');
    } else {
      isLoggedIn.value = false;
      localStorage.setItem('isLoggedIn', 'false');
      throw new Error('无效的用户名或密码');
    }
  };

  const logout = () => {
    isLoggedIn.value = false;
    localStorage.setItem('isLoggedIn', 'false');
  };

  return { isLoggedIn, login, logout };
});
