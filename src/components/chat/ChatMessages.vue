<script setup lang="ts">
import type { ChatMessage } from '@/types';
import { Loading } from '@element-plus/icons-vue';
import { ElIcon } from 'element-plus';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import AssistantMessage from './message/AssistantMessage.vue';
import AssistantSuggestions from './message/AssistantSuggestions.vue';
import UserMessage from './message/UserMessage.vue';

type ChatMessageWithSuggestions = ChatMessage & { loading?: boolean, suggestions?: string[]; };

const props = defineProps<{
  messages: ChatMessageWithSuggestions[];
  currentSessionId?: string;
  currentDatasetExists: boolean;
}>();

const emit = defineEmits<{
  'add-sample-question': [question: string]; // 添加建议问题到输入框
}>();

const messagesContainer = ref<HTMLElement | null>(null);

const lastMessage = computed(() => props.messages.length ? props.messages[props.messages.length - 1] : null);

// 滚动到底部
const scrollToBottom = (): void => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
};

defineExpose({
  scrollToBottom, // 暴露滚动到底部方法
});

// 监听消息变化，自动滚动到底部
watch(() => props.messages.length, () => {
  scrollToBottom();
});

// 监听具体消息内容变化（如：流式响应）
watch(() => props.messages, () => {
  scrollToBottom();
}, { deep: true });

// 组件挂载后滚动到底部
onMounted(() => {
  scrollToBottom();
});
</script>

<template>
  <div class="chat-messages" ref="messagesContainer">

    <!-- 空状态：无会话或无数据集 -->
    <div v-if="!currentSessionId || !currentDatasetExists" class="empty-state">
      <div class="empty-message">
        <p>选择一个数据集，开始您的数据分析对话</p>
      </div>
    </div>

    <!-- 空状态：有会话但无消息 -->
    <div v-else-if="!messages.length" class="empty-state">
      <div class="empty-message">
        <p>输入分析需求，开始您的数据分析对话</p>
      </div>
    </div>

    <!-- 消息列表 -->
    <template v-else>
      <div v-for="(message, index) in messages" :key="index">
        <AssistantMessage v-if="message.type === 'assistant'" :message="message" />
        <UserMessage v-else :content="message.content" />
      </div>
      <!-- 最后一条 AI 消息的加载状态和建议按钮 -->
      <template v-if="lastMessage?.type === 'assistant'">
        <!-- 加载状态 -->
        <div v-if="lastMessage.loading" class="message-loading">
          <el-icon>
            <Loading class="rotating" />
          </el-icon>
          <span>正在处理...</span>
        </div>
        <!-- 建议按钮 -->
        <AssistantSuggestions v-if="!lastMessage.loading && lastMessage.suggestions?.length"
          :suggestions="lastMessage.suggestions" @set="emit('add-sample-question', $event)" />
      </template>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.chat-messages {
  flex-grow: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  background: #ffffff;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;

    &:hover {
      background: #a8a8a8;
    }
  }
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #6b7280;

  .empty-message {
    text-align: center;
    max-width: 400px;
    padding: 40px 20px;

    p {
      font-size: 16px;
      color: #6b7280;
      margin: 0;
      line-height: 1.6;
    }
  }
}

.message-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  margin: 8px 0;
  font-size: 14px;

  .el-icon {
    font-size: 16px;
  }
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.rotating {
  animation: rotating 2s linear infinite;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .chat-messages {
    padding: 16px;
  }

  .user-message {
    max-width: 85%;
  }
}
</style>
