<script setup lang="ts">
interface Props {
  title: string;
  subtitle: string;
}

defineProps<Props>();
</script>

<template>
  <div>
    <h1 class="title">{{ title }}</h1>
    <p class="subtitle">{{ subtitle }}</p>
  </div>
</template>

<style scoped>
.title {
  margin: 0 0 8px 0;
  font-size: 32px;
  font-weight: 700;
  color: #1f2937;
}

.subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 16px;
  font-weight: 400;
}
</style>
