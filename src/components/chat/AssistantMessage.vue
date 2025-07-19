<script setup lang="ts">
import AssistantMessageText from '@/components/chat/AssistantMessageText.vue';
import type { AssistantChatMessage } from '@/types';
import { ref } from 'vue';

defineProps<{
  message: AssistantChatMessage & { loading?: boolean; };
}>();

const parsePossibleJsonString = (value: any) => {
  try {
    const obj = JSON.parse(value);
    return JSON.stringify(obj, null, 2);
  } catch (_: unknown) {
    return value;
  }
};

// 用于管理工具调用的折叠状态
interface ExpandState {
  args: boolean;
  result: boolean;
  artifact: boolean;
  error: boolean;
}
const expandedTools = ref<Record<string, boolean>>({});
const expandedSections = ref<Record<string, ExpandState>>({});

// 切换工具调用的展开/折叠状态
const toggleToolExpand = (id: string) => {
  expandedTools.value[id] = !expandedTools.value[id];
};

// 切换工具调用内部各部分的展开/折叠状态
const toggleSectionExpand = (toolId: string, section: keyof ExpandState) => {
  if (!expandedSections.value[toolId]) {
    expandedSections.value[toolId] = {
      args: false,
      result: false,
      artifact: false,
      error: false,
    };
  }
  expandedSections.value[toolId][section] = !expandedSections.value[toolId][section];
};

// 检查工具调用是否展开
const isToolExpanded = (toolId: string) => {
  return !!expandedTools.value[toolId];
};

// 检查工具调用内部部分是否展开
const isSectionExpanded = (toolId: string, section: keyof ExpandState) => {
  return expandedSections.value[toolId]?.[section] || false;
};
</script>

<template>
  <div v-for="(part, partIndex) in message.content" :key="partIndex">
    <div v-if="part.type === 'text'" class="text-container">
      <AssistantMessageText class="assistant-text" :md="part.content.replace('\n\n', '\n')"></AssistantMessageText>
    </div>
    <div v-else-if="part.type === 'tool_call'">
      <div v-if="message.tool_calls && part.id in message.tool_calls"
        :class="['tool-call', message.tool_calls[part.id].status]">
        <div class="tool-header" @click="toggleToolExpand(part.id)">
          <el-icon v-if="message.tool_calls[part.id].status === 'running'">
            <Loading class="rotating" />
          </el-icon>
          <el-icon v-else-if="message.tool_calls[part.id].status === 'success'" style="color: #67C23A">
            <Check />
          </el-icon>
          <el-icon v-else-if="message.tool_calls[part.id].status === 'error'" style="color: #F56C6C">
            <WarningFilled />
          </el-icon>
          {{ message.tool_calls[part.id].name }}
          <div class="expand-icon">
            <el-icon>
              <ArrowDown v-if="isToolExpanded(part.id)" />
              <ArrowRight v-else />
            </el-icon>
          </div>
        </div>

        <div v-if="isToolExpanded(part.id)" class="tool-content">
          <div class="tool-section-header" @click="toggleSectionExpand(part.id, 'args')">
            <span>参数</span>
            <el-icon>
              <ArrowDown v-if="isSectionExpanded(part.id, 'args')" />
              <ArrowRight v-else />
            </el-icon>
          </div>
          <div v-if="isSectionExpanded(part.id, 'args')" class="tool-args">
            <pre>{{ parsePossibleJsonString(message.tool_calls[part.id].args) }}</pre>
          </div>

          <div v-if="message.tool_calls[part.id].result">
            <div class="tool-section-header" @click="toggleSectionExpand(part.id, 'result')">
              <span>结果</span>
              <el-icon>
                <ArrowDown v-if="isSectionExpanded(part.id, 'result')" />
                <ArrowRight v-else />
              </el-icon>
            </div>
            <div v-if="isSectionExpanded(part.id, 'result')" class="tool-result">
              <pre>{{ parsePossibleJsonString(message.tool_calls[part.id].result) }}</pre>
            </div>
          </div>

          <div v-if="message.tool_calls[part.id].artifact" class="tool-artifact">
            <div class="tool-section-header" @click="toggleSectionExpand(part.id, 'artifact')">
              <span>生成内容</span>
              <el-icon>
                <ArrowDown v-if="isSectionExpanded(part.id, 'artifact')" />
                <ArrowRight v-else />
              </el-icon>
            </div>
            <div v-if="isSectionExpanded(part.id, 'artifact')">
              <div v-if="message.tool_calls[part.id].artifact?.type === 'image'" class="image-artifact">
                <img :src="`data:image/png;base64,${message.tool_calls[part.id].artifact?.base64_data}`"
                  alt="Generated chart" style="max-width: 100%;" />
                <div v-if="message.tool_calls[part.id].artifact?.caption" class="image-caption">
                  {{ message.tool_calls[part.id].artifact?.caption }}
                </div>
              </div>
            </div>
          </div>

          <div v-if="message.tool_calls[part.id].error">
            <div class="tool-section-header" @click="toggleSectionExpand(part.id, 'error')">
              <span>错误</span>
              <el-icon>
                <ArrowDown v-if="isSectionExpanded(part.id, 'error')" />
                <ArrowRight v-else />
              </el-icon>
            </div>
            <div v-if="isSectionExpanded(part.id, 'error')" class="tool-error">
              <pre>{{ message.tool_calls[part.id].error }}</pre>
            </div>
          </div>

        </div>
      </div>
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

/* 覆盖一些 GitHub 样式以更好地适应聊天界面 */
:deep(.markdown-body) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: transparent;
  font-size: 14px;
  color: #374151;

  /* 调整代码块样式 */
  pre {
    background-color: #f6f8fa;
    border-radius: 8px;
    padding: 12px;
    border: 1px solid #e1e5e9;
    overflow-x: auto;
  }

  code {
    background-color: #f6f8fa;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 13px;
  }

  /* 调整表格样式 */
  table {
    display: table;
    width: 100%;
    overflow-x: auto;
    border-collapse: collapse;
    margin: 12px 0;
  }

  table th,
  table td {
    padding: 8px 12px;
    border: 1px solid #e1e5e9;
    text-align: left;
  }

  table th {
    background-color: #f6f8fa;
    font-weight: 600;
  }

  /* 调整图片最大宽度 */
  img {
    max-width: 100%;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  /* 调整标题样式 */
  h1,
  h2,
  h3,
  h4,
  h5,
  h6 {
    color: #1f2937;
    font-weight: 600;
  }

  /* 调整链接样式 */
  a {
    color: #10b981;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  /* 调整列表样式 */
  ul,
  ol {
    margin: 8px 0;
    padding-left: 20px;
  }

  li {
    margin: 4px 0;
  }

  /* 调整引用样式 */
  blockquote {
    margin: 12px 0;
    padding: 8px 12px;
    background-color: #f9fafb;
    border-left: 4px solid #10b981;
    border-radius: 4px;
  }
}

/* 工具调用样式 */
.tool-call {
  background: #ffffff;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);

  &.running {
    border-left: 4px solid #f59e0b;
    background: #fffbeb;
  }

  &.success {
    border-left: 4px solid #10b981;
    background: #f0fdf4;
  }

  &.error {
    border-left: 4px solid #ef4444;
    background: #fef2f2;
  }
}

.tool-header {
  display: flex;
  align-items: center;
  font-weight: 600;
  margin-bottom: 12px;
  cursor: pointer;
  user-select: none;
  color: #374151;
  font-size: 14px;

  .el-icon {
    margin-right: 8px;
    color: #6b7280;
  }
}

.expand-icon {
  margin-left: auto;
  color: #6b7280;
  transition: transform 0.2s ease;
}

.tool-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #f8fafc;
  border-radius: 6px;
  margin: 8px 0;
  cursor: pointer;
  user-select: none;
  font-weight: 500;
  color: #4b5563;
  font-size: 13px;
  transition: all 0.2s ease;

  &:hover {
    background-color: #e2e8f0;
  }
}

.tool-content {
  margin-top: 12px;
  margin-left: 0;
}

.tool-args {
  background: #f0f9ff;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
  border-left: 3px solid #3b82f6;

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
    color: #1e40af;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
  }
}

.tool-result {
  background: #f0fdf4;
  padding: 12px;
  border-radius: 6px;
  border-left: 3px solid #10b981;

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
    color: #166534;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
  }
}

.tool-error {
  background: #fef2f2;
  padding: 12px;
  border-radius: 6px;
  border-left: 3px solid #ef4444;

  pre {
    margin: 0;
    white-space: pre-wrap;
    font-size: 12px;
    color: #dc2626;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
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
  margin-top: 12px;
}

.image-artifact {
  text-align: center;
  padding: 16px;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;

  img {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }
}

.image-caption {
  margin-top: 12px;
  font-style: italic;
  color: #6b7280;
  font-size: 13px;
}
</style>
