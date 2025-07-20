<script setup lang="ts">
import type { AssistantChatMessage } from '@/types';
import AssistantToolCall from './AssistantToolCall.vue';
import AssistantText from './AssistantText.vue';

defineProps<{
  message: AssistantChatMessage & { loading?: boolean; };
}>();
</script>

<template>
  <div v-for="(part, partIndex) in message.content" :key="partIndex">
    <div v-if="part.type === 'text'" class="text-container">
      <AssistantText class="assistant-text" :md="part.content.replace('\n\n', '\n')" />
    </div>
    <div v-else-if="part.type === 'tool_call' && message.tool_calls?.[part.id]">
      <AssistantToolCall :data="message.tool_calls[part.id]" />
    </div>
  </div>
</template>

<style scoped>
.text-container {
  margin: 16px;
  margin-bottom: 10px;
}

.assistant-text {
  line-height: 1.5;
  color: #374151;
  font-size: 14px;
}
</style>
