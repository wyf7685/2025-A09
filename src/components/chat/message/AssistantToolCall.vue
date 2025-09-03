<script setup lang="ts">
import type { ToolCall } from '@/types';
import { base64ToBlob, parsePossibleJsonString } from '@/utils/tools';
import { ArrowDown, ArrowRight, Check, Loading, WarningFilled } from '@element-plus/icons-vue';
import { ElIcon } from 'element-plus';
import { computed, onUnmounted, reactive, ref, watch } from 'vue';

const props = defineProps<{
  data: ToolCall;
}>();

const isExpanded = ref(false);
const sectionExpanded = reactive({
  args: false,
  result: false,
  artifact: false,
  error: false,
});
const artifactImageUrl = ref<string>('');

const statusIconMap = {
  running: Loading,
  success: Check,
  error: WarningFilled,
};

const status = computed(() => props.data.status);
const statusIcon = computed(() => statusIconMap[props.data.status]);
const name = computed(() => props.data.name);
const args = computed(() => props.data.args);
const result = computed(() => props.data.result || null);
const artifact = computed(() => props.data.artifact || null);
const error = computed(() => props.data.error || null);

const removeCurrentUrl = () => {
  if (artifactImageUrl.value) {
    URL.revokeObjectURL(artifactImageUrl.value);
    artifactImageUrl.value = '';
  }
};

watch(() => artifact.value?.base64_data, (newValue) => {
  if (newValue && artifact.value?.type === 'image') {
    removeCurrentUrl();
    const blob = base64ToBlob(newValue);
    if (blob) {
      artifactImageUrl.value = URL.createObjectURL(blob);
      // 默认展开图片生成内容
      isExpanded.value = sectionExpanded.artifact = true;
    } else {
      console.error('无法将 Base64 数据转换为 Blob 对象');
    }
  } else {
    removeCurrentUrl();
  }
});

onUnmounted(() => removeCurrentUrl());
</script>

<template>
  <div :class="['tool-call', status]">
    <!-- Header -->
    <div class="tool-header" @click="isExpanded = !isExpanded">
      <el-icon>
        <component :is="statusIcon" :class="{ rotating: status === 'running' }" />
      </el-icon>
      {{ name }}
      <div class="expand-icon">
        <el-icon>
          <ArrowDown v-if="isExpanded" />
          <ArrowRight v-else />
        </el-icon>
      </div>
    </div>

    <!-- Content -->
    <div v-if="isExpanded" class="tool-content">
      <!-- Args -->
      <div class="tool-section-header" @click="sectionExpanded.args = !sectionExpanded.args">
        <span>参数</span>
        <el-icon>
          <ArrowDown v-if="sectionExpanded.args" />
          <ArrowRight v-else />
        </el-icon>
      </div>
      <div v-if="sectionExpanded.args" class="tool-args">
        <pre>{{ parsePossibleJsonString(args) }}</pre>
      </div>

      <!-- Result -->
      <div v-if="result">
        <div class="tool-section-header" @click="sectionExpanded.result = !sectionExpanded.result">
          <span>结果</span>
          <el-icon>
            <ArrowDown v-if="sectionExpanded.result" />
            <ArrowRight v-else />
          </el-icon>
        </div>
        <div v-if="sectionExpanded.result" class="tool-result">
          <pre>{{ parsePossibleJsonString(result) }}</pre>
        </div>
      </div>

      <!-- Artifact -->
      <div v-if="artifact" class="tool-artifact">
        <div class="tool-section-header" @click="sectionExpanded.artifact = !sectionExpanded.artifact">
          <span>生成内容</span>
          <el-icon>
            <ArrowDown v-if="sectionExpanded.artifact" />
            <ArrowRight v-else />
          </el-icon>
        </div>
        <div v-if="sectionExpanded.artifact">
          <div v-if="artifact.type === 'image'" class="image-artifact">
            <img :src="artifactImageUrl" :alt="artifact.caption || 'Generated chart'" style="max-width: 100%;" />
            <div v-if="artifact.caption" class="image-caption">
              {{ artifact.caption }}
            </div>
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-if="error">
        <div class="tool-section-header" @click="sectionExpanded.error = !sectionExpanded.error">
          <span>错误</span>
          <el-icon>
            <ArrowDown v-if="sectionExpanded.error" />
            <ArrowRight v-else />
          </el-icon>
        </div>
        <div v-if="sectionExpanded.error" class="tool-error">
          <pre>{{ error }}</pre>
        </div>
      </div>

    </div> <!-- End of Content -->
  </div>
</template>

<style scoped>
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

    .el-icon {
      color: #6B7280;
    }
  }

  &.success {
    border-left: 4px solid #10b981;
    background: #f0fdf4;

    .el-icon {
      color: #67C23A;
    }
  }

  &.error {
    border-left: 4px solid #ef4444;
    background: #fef2f2;

    .el-icon {
      color: #F56C6C;
    }
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
