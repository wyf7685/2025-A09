<script setup lang="ts">
import { RouterView, useRoute, useRouter } from 'vue-router';

const router = useRouter();
const route = useRoute();
</script>

<template>
  <RouterView v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </RouterView>
</template>

<style>
@import '@/assets/styles/global.css';
@import '@/assets/styles/element-override.css';

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
