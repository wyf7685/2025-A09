<script setup lang="ts">
import MainLayout from '@/layouts/MainLayout.vue';
import { useLoginStore } from '@/stores/login';
import LoginView from '@/views/LoginView.vue';
import { checkHealth as checkHealthApi } from '@/utils/api';
import { onMounted, ref } from 'vue';

const loginStore = useLoginStore();

const apiStatus = ref(false);

const checkHealth = async () => {
  try {
    await checkHealthApi();
    apiStatus.value = true;
  } catch (error) {
    console.error('健康检查失败:', error);
    apiStatus.value = false;
  }
};

// 生命周期
onMounted(async () => {
  await checkHealth();

  // 定期检查健康状态
  setInterval(checkHealth, 3 * 60 * 1000);
});
</script>

<template>
  <LoginView v-if="!loginStore.isLoggedIn" :apiStatus="apiStatus" />
  <MainLayout v-else :apiStatus="apiStatus">
    <RouterView v-slot="{ Component }">
      <template v-if="Component">
        <Transition mode="out-in">
          <KeepAlive>
            <Suspense>
              <!-- 主要内容 -->
              <component :is="Component"></component>
              <!-- 加载中状态 -->
              <template #fallback>
                正在加载...
              </template>
            </Suspense>
          </KeepAlive>
        </Transition>
      </template>
    </RouterView>
  </MainLayout>
</template>
