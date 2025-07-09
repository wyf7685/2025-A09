<script setup lang="ts">
import type { AssistantChatMessage } from '@/types';
import { formatMessage } from '@/utils/tools';
import { ref, watch } from 'vue';

const props = defineProps<{
  message: AssistantChatMessage & { loading?: boolean };
}>();

// 为每个文本部分创建一个格式化后的内容
const formattedContents = ref<Record<number, string>>({});

// 监听消息内容变化，异步格式化每个文本部分
watch(() => props.message.content, async (newContent) => {
  if (!newContent) return;

  for (let i = 0; i < newContent.length; i++) {
    const part = newContent[i];
    if (part.type === 'text') {
      formattedContents.value[i] = await formatMessage(part.content);
    }
  }
}, { immediate: true });

const parseJsonString = (value: any) => {
  try {
    const obj = JSON.parse(value);
    return JSON.stringify(obj, null, 2);
  } catch (_: unknown) {
    return value;
  }
}
</script>

<template>
  <div v-for="(part, partIndex) in message.content" :key="partIndex">
    <div v-if="part.type === 'text'" class="text-container">
      <div v-if="formattedContents[partIndex]" class="assistant-text markdown-body"
        v-html="formattedContents[partIndex]"></div>
      <div v-else class="assistant-text">{{ part.content }}</div>
    </div>
    <div v-else-if="part.type === 'tool_call'">
      <div v-if="message.tool_calls && part.id in message.tool_calls"
        :class="['tool-call', message.tool_calls[part.id].status]">
        <div class="tool-header">
          <el-icon v-if="message.tool_calls[part.id].status === 'running'">
            <Loading class="rotating" />
          </el-icon>
          <el-icon v-else-if="message.tool_calls[part.id].status === 'success'" style="color: #67C23A">
            <Check />
          </el-icon>
          <el-icon v-else-if="message.tool_calls[part.id].status === 'error'" style="color: #F56C6C">
            <WarningFilled />
          </el-icon>
          <strong>{{ message.tool_calls[part.id].name }}</strong>
        </div>

        <div class="tool-args">
          <pre>{{ parseJsonString(message.tool_calls[part.id].args) }}</pre>
        </div>

        <div v-if="message.tool_calls[part.id].result" class="tool-result">
          <div class="result-label">结果:</div>
          <pre>{{ parseJsonString(message.tool_calls[part.id].result) }}</pre>
        </div>

        <div v-if="message.tool_calls[part.id].artifact" class="tool-artifact">
          <div v-if="message.tool_calls[part.id].artifact?.type === 'image'" class="image-artifact">
            <img :src="`data:image/png;base64,${message.tool_calls[part.id].artifact?.base64_data}`"
              alt="Generated chart" style="max-width: 100%;" />
            <div v-if="message.tool_calls[part.id].artifact?.caption" class="image-caption">
              {{ message.tool_calls[part.id].artifact?.caption }}
            </div>
          </div>
        </div>

        <div v-if="message.tool_calls[part.id].error" class="tool-error">
          <div class="error-label">错误:</div>
          <pre>{{ message.tool_calls[part.id].error }}</pre>
        </div>
      </div>
    </div>

  </div>
  <div v-if="message.loading">
    <el-icon>
      <Loading class="rotating" />
    </el-icon>
    正在处理...
  </div>
</template>

<style scoped>
.text-container {
  margin: 16px;
  margin-bottom: 10px;
}

.assistant-text {
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 覆盖一些 GitHub 样式以更好地适应聊天界面 */
:deep(.markdown-body) {
  font-family: inherit;
  background-color: transparent;
  font-size: 14px;

  /* 调整代码块样式 */
  pre {
    background-color: #f6f8fa;
    border-radius: 6px;
  }

  /* 调整表格样式 */
  table {
    display: table;
    width: 100%;
    overflow-x: auto;
  }

  /* 调整图片最大宽度 */
  img {
    max-width: 100%;
  }
}

/* 工具调用样式 */
.tool-call {
  background: #f9f9f9;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
  border-left: 3px solid #909399;

  &.running {
    border-left-color: #E6A23C;
  }

  &.success {
    border-left-color: #67C23A;
  }

  &.error {
    border-left-color: #F56C6C;
  }
}

.tool-header {
  display: flex;
  align-items: center;
  font-weight: bold;
  margin-bottom: 5px;

  .el-icon {
    margin-right: 5px;
  }
}

.tool-args {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 8px;

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
  }
}

.tool-result {
  background: #f0f9eb;
  padding: 8px;
  border-radius: 4px;

  .result-label {
    font-weight: bold;
    color: #67C23A;
    margin-bottom: 5px;
  }

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
  }
}

.tool-error {
  background: #fef0f0;
  padding: 8px;
  border-radius: 4px;

  .error-label {
    font-weight: bold;
    color: #F56C6C;
    margin-bottom: 5px;
  }

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
    color: #F56C6C;
  }
}

.rotating {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.tool-artifact {
  margin-top: 10px;
}

.image-artifact {
  text-align: center;
}

.image-caption {
  margin-top: 5px;
  font-style: italic;
  color: #666;
}
</style>
