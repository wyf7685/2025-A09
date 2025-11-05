<script setup lang="ts">
defineProps<{
  content: string;
}>();
</script>

<template>
  <div class="user-message-container">
    <pre class="user-message">{{ content }}</pre>
  </div>
</template>

<style scoped>
.user-message-container {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.user-message {
  background: #f3f4f6;
  color: #1f2937;
  padding: 12px 16px;
  border-radius: 18px 18px 6px 18px;
  max-width: 70%;
  word-wrap: break-word;
  font-size: 14px;
  line-height: 1.5;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
}
</style>
