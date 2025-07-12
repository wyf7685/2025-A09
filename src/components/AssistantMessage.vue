<script setup lang="ts">
import type { AssistantChatMessage } from '@/types';
import AssistantMessageText from '@/components/AssistantMessageText.vue'
import { ref } from 'vue';

const props = defineProps<{
  message: AssistantChatMessage & { loading?: boolean };
}>();

const parsePossibleJsonString = (value: any) => {
  try {
    const obj = JSON.parse(value);
    return JSON.stringify(obj, null, 2);
  } catch (_: unknown) {
    return value;
  }
}

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
  line-height: 1.3;
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
  cursor: pointer;
  user-select: none;

  .el-icon {
    margin-right: 5px;
  }
}

.expand-icon {
  margin-left: auto;
}

.tool-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px;
  background-color: #f0f0f0;
  border-radius: 4px;
  margin: 5px 0;
  cursor: pointer;
  user-select: none;
  font-weight: bold;
}

.tool-content {
  margin-top: 8px;
  margin-left: 8px;
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
  margin-top: 5px;
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
