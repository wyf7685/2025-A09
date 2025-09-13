<script setup lang="ts">
import type { ToolCall } from '@/types';
import { base64ToBlob, parsePossibleJsonString } from '@/utils/tools';
import { ArrowDown, ArrowRight, Check, Loading, WarningFilled, View, Close } from '@element-plus/icons-vue';
import { ElIcon, ElButton, ElDialog, ElTabPane, ElTabs } from 'element-plus';
import { computed, onUnmounted, reactive, ref, watch } from 'vue';

const props = defineProps<{
  data: ToolCall;
}>();

const isExpanded = ref(false);
const showDetailDialog = ref(false);
const activeTab = ref('description');
const sectionExpanded = reactive({
  args: false,
  result: false,
  artifact: false,
  error: false,
});
const artifactImageUrl = ref<string>('');
const imageLoadError = ref(false);

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

// 获取工具的描述信息
const getToolDescription = (toolName: string) => {
  const descriptions: Record<string, string> = {
    'correlationAnalysis': '生成数据相关性分析热力图。我会生成一个交互式的相关性热力图，这个组件包含以下特性：\n\n主要功能：\n1. 随机数据生成 - 模拟了6个业务指标的数据（销售额、广告投入、客户满意度、员工数量、市场份额、研发投入）\n2. 相关性计算 - 自动计算尔逊相关系数矩阵\n3. 热力图可视化 - 用颜色深浅表示相关性强度\n4. 交互式功能 - 鼠标悬停显示详细数值，可重新生成数据\n\n视觉设计：\n• 颜色编码：红色系表示正相关，蓝色系表示负相关\n• 强度表示：颜色越深表示相关性越强\n• 清晰标签：包含变量名称和数值显示',
    'dataAnalysis': '执行数据分析任务，包括统计计算、数据清洗和基础分析',
    'chartGeneration': '生成各种类型的数据可视化图表',
    'default': '执行数据处理工具'
  };
  return descriptions[toolName] || descriptions['default'];
};

const removeCurrentUrl = () => {
  if (artifactImageUrl.value) {
    URL.revokeObjectURL(artifactImageUrl.value);
    artifactImageUrl.value = '';
  }
  imageLoadError.value = false;
};

// 增强的 base64 转换函数
const createImageUrl = (base64Data: string) => {
  try {
    // 重置错误状态
    imageLoadError.value = false;

    // 如果数据已经是一个 URL，直接使用
    if (base64Data.startsWith('http') || base64Data.startsWith('blob:')) {
      return base64Data;
    }

    // 处理 data URL
    if (base64Data.startsWith('data:')) {
      return base64Data;
    }

    // 处理纯 base64 数据
    let mimeType = 'image/png'; // 默认类型

    // 尝试从 base64 数据推断类型
    if (base64Data.startsWith('/9j/')) {
      mimeType = 'image/jpeg';
    } else if (base64Data.startsWith('iVBORw0KGgo')) {
      mimeType = 'image/png';
    } else if (base64Data.startsWith('R0lGODlh')) {
      mimeType = 'image/gif';
    } else if (base64Data.startsWith('UklGR')) {
      mimeType = 'image/webp';
    }

    // 创建 data URL
    const dataUrl = `data:${mimeType};base64,${base64Data}`;

    // 验证 base64 数据
    try {
      atob(base64Data);
      return dataUrl;
    } catch (e) {
      console.error('Invalid base64 data:', e);
      imageLoadError.value = true;
      return '';
    }
  } catch (error) {
    console.error('Error creating image URL:', error);
    imageLoadError.value = true;
    return '';
  }
};

const onImageError = () => {
  console.error('图片加载失败');
  imageLoadError.value = true;
};

const onImageLoad = () => {
  imageLoadError.value = false;
};

watch(() => artifact.value?.base64_data, (newValue) => {
  removeCurrentUrl();

  if (newValue && artifact.value?.type === 'image') {
    // 使用增强的图片 URL 创建函数
    artifactImageUrl.value = createImageUrl(newValue);
  }
}, { immediate: true });

onUnmounted(() => removeCurrentUrl());
</script>

<template>
  <div :class="['claude-tool-call', status]">
    <!-- 主要显示区域 - 类似 Claude 左侧 -->
    <div class="tool-main-content">
      <!-- 工具头部 -->
      <div class="tool-header">
        <el-icon>
          <component :is="statusIcon" :class="{ rotating: status === 'running' }" />
        </el-icon>
        <span class="tool-name">{{ name }}</span>
        <span class="tool-status">Interactive artifact</span>
        <el-button
          class="detail-button"
          size="small"
          text
          @click="showDetailDialog = true"
        >
          <el-icon><View /></el-icon>
        </el-button>
      </div>

      <!-- 工具描述 -->
      <div class="tool-description">
        <p>{{ getToolDescription(name) }}</p>
      </div>

      <!-- 生成的内容预览 -->
      <div v-if="artifact && artifact.type === 'image'" class="artifact-preview">
        <div v-if="!imageLoadError && artifactImageUrl" class="image-container">
          <img
            :src="artifactImageUrl"
            :alt="artifact.caption || 'Generated chart'"
            @error="onImageError"
            @load="onImageLoad"
          />
        </div>
        <div v-else-if="imageLoadError" class="image-error">
          <el-icon><WarningFilled /></el-icon>
          <span>图片加载失败</span>
          <div class="error-details">
            <p>可能的原因：</p>
            <ul>
              <li>Base64 数据格式错误</li>
              <li>图片数据损坏</li>
              <li>浏览器不支持该图片格式</li>
            </ul>
          </div>
        </div>
        <div v-else class="image-loading">
          <el-icon><Loading class="rotating" /></el-icon>
          <span>正在加载图片...</span>
        </div>
        <div v-if="artifact.caption" class="artifact-caption">
          {{ artifact.caption }}
        </div>
      </div>

      <!-- 结果预览（文本形式） -->
      <div v-else-if="result && status === 'success'" class="result-preview">
        <div class="result-summary">
          工具执行完成，点击右上角按钮查看详细信息
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="error" class="error-preview">
        <el-icon><WarningFilled /></el-icon>
        <span>工具执行出错，点击查看详细信息</span>
      </div>

      <!-- 运行状态 -->
      <div v-if="status === 'running'" class="running-status">
        <el-icon><Loading class="rotating" /></el-icon>
        <span>正在执行工具...</span>
      </div>
    </div>

    <!-- 详细信息弹窗 - 类似 Claude 右侧展开 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="name"
      width="80%"
      :before-close="() => showDetailDialog = false"
    >
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- 描述标签页 -->
        <el-tab-pane label="描述" name="description">
          <div class="tab-content">
            <h3>工具功能</h3>
            <pre class="description-text">{{ getToolDescription(name) }}</pre>
          </div>
        </el-tab-pane>

        <!-- 参数标签页 -->
        <el-tab-pane label="调用参数" name="args">
          <div class="tab-content">
            <h3>输入参数</h3>
            <pre class="code-block">{{ parsePossibleJsonString(args) }}</pre>
          </div>
        </el-tab-pane>

        <!-- 结果标签页 -->
        <el-tab-pane v-if="result" label="返回结果" name="result">
          <div class="tab-content">
            <h3>执行结果</h3>
            <pre class="code-block result">{{ parsePossibleJsonString(result) }}</pre>
          </div>
        </el-tab-pane>

        <!-- 生成内容标签页 -->
        <el-tab-pane v-if="artifact" label="生成内容" name="artifact">
          <div class="tab-content">
            <h3>生成的内容</h3>
            <div v-if="artifact.type === 'image'" class="artifact-full">
              <div v-if="!imageLoadError && artifactImageUrl" class="image-container">
                <img
                  :src="artifactImageUrl"
                  :alt="artifact.caption || 'Generated chart'"
                  @error="onImageError"
                  @load="onImageLoad"
                />
              </div>
              <div v-else-if="imageLoadError" class="image-error">
                <el-icon><WarningFilled /></el-icon>
                <span>图片加载失败</span>
                <div class="error-details">
                  <p>调试信息：</p>
                  <pre class="debug-info">{{ JSON.stringify({
                    hasBase64Data: !!artifact.base64_data,
                    dataLength: artifact.base64_data?.length,
                    dataStart: artifact.base64_data?.substring(0, 50),
                    artifactType: artifact.type
                  }, null, 2) }}</pre>
                </div>
              </div>
              <div v-else class="image-loading">
                <el-icon><Loading class="rotating" /></el-icon>
                <span>正在加载图片...</span>
              </div>
              <div v-if="artifact.caption" class="artifact-caption">
                {{ artifact.caption }}
              </div>
            </div>
            <div v-else class="artifact-data">
              <pre class="code-block">{{ JSON.stringify(artifact, null, 2) }}</pre>
            </div>
          </div>
        </el-tab-pane>


        <!-- 错误信息标签页 -->
        <el-tab-pane v-if="error" label="错误信息" name="error">
          <div class="tab-content">
            <h3>错误详情</h3>
            <pre class="code-block error">{{ error }}</pre>
          </div>
        </el-tab-pane>

      </el-tabs>

      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* Claude 风格的工具调用组件 */
.claude-tool-call {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  margin: 16px 0;
  overflow: hidden;
  transition: all 0.2s ease;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  &.running {
    border-left: 4px solid #f59e0b;
    background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%);
  }

  &.success {
    border-left: 4px solid #10b981;
    background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%);
  }

  &.error {
    border-left: 4px solid #ef4444;
    background: linear-gradient(135deg, #fef2f2 0%, #ffffff 100%);
  }
}

.tool-main-content {
  padding: 20px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;

  .el-icon {
    font-size: 18px;
    color: #6b7280;
  }

  .tool-name {
    font-weight: 600;
    color: #111827;
    font-size: 16px;
  }

  .tool-status {
    color: #6b7280;
    font-size: 14px;
    background: #f1f5f9;
    padding: 4px 8px;
    border-radius: 6px;
    font-weight: 500;
  }

  .detail-button {
    margin-left: auto;
    color: #6b7280;

    &:hover {
      color: #374151;
      background: #f9fafb;
    }
  }
}

.tool-description {
  margin-bottom: 20px;

  p {
    margin: 0;
    color: #374151;
    line-height: 1.6;
    font-size: 14px;
    white-space: pre-line;
  }
}

.artifact-preview {
  margin-top: 16px;
  text-align: center;
  background: #f9fafb;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e5e7eb;

  .image-container {
    img {
      max-width: 100%;
      height: auto;
      border-radius: 8px;
      box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
      transition: opacity 0.3s ease;
    }
  }

  .image-error {
    padding: 20px;
    color: #dc2626;
    text-align: center;

    .el-icon {
      font-size: 24px;
      margin-bottom: 8px;
    }

    span {
      display: block;
      font-size: 16px;
      font-weight: 500;
      margin-bottom: 12px;
    }

    .error-details {
      text-align: left;
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 6px;
      padding: 12px;
      margin-top: 12px;

      p {
        margin: 0 0 8px 0;
        font-weight: 500;
        color: #991b1b;
      }

      ul {
        margin: 0;
        padding-left: 20px;
        color: #7f1d1d;

        li {
          margin: 4px 0;
          font-size: 14px;
        }
      }

      .debug-info {
        background: #1f2937;
        color: #f9fafb;
        padding: 8px;
        border-radius: 4px;
        font-size: 12px;
        margin-top: 8px;
        text-align: left;
        overflow-x: auto;
      }
    }
  }

  .image-loading {
    padding: 20px;
    color: #6b7280;
    text-align: center;

    .el-icon {
      font-size: 24px;
      margin-bottom: 8px;
      color: #d97706;
    }

    span {
      display: block;
      font-size: 14px;
    }
  }
}

.artifact-caption {
  margin-top: 12px;
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
}

.result-preview {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f0fdf4;
  border-radius: 8px;
  border-left: 4px solid #10b981;

  .result-summary {
    color: #166534;
    font-size: 14px;
    font-weight: 500;
  }
}

.error-preview {
  margin-top: 16px;
  padding: 12px 16px;
  background: #fef2f2;
  border-radius: 8px;
  border-left: 4px solid #ef4444;
  display: flex;
  align-items: center;
  gap: 8px;

  .el-icon {
    color: #dc2626;
    font-size: 16px;
  }

  span {
    color: #dc2626;
    font-size: 14px;
    font-weight: 500;
  }
}

.running-status {
  margin-top: 16px;
  padding: 12px 16px;
  background: #fffbeb;
  border-radius: 8px;
  border-left: 4px solid #f59e0b;
  display: flex;
  align-items: center;
  gap: 8px;

  .el-icon {
    color: #d97706;
    font-size: 16px;
  }

  span {
    color: #d97706;
    font-size: 14px;
    font-weight: 500;
  }
}

/* 弹窗样式 */
:deep(.el-dialog) {
  border-radius: 12px;
  overflow: hidden;
}

:deep(.el-dialog__header) {
  background: #f8fafc;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.el-dialog__title) {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

:deep(.el-dialog__body) {
  padding: 0;
}

.detail-tabs {
  :deep(.el-tabs__header) {
    margin: 0;
    background: #ffffff;
    border-bottom: 1px solid #e5e7eb;
    padding: 0 24px;
  }

  :deep(.el-tabs__nav-wrap) {
    padding: 0;
  }

  :deep(.el-tabs__item) {
    padding: 16px 0;
    margin-right: 32px;
    font-weight: 500;
    color: #6b7280;

    &.is-active {
      color: #3b82f6;
    }
  }

  :deep(.el-tabs__active-bar) {
    background-color: #3b82f6;
  }
}

.tab-content {
  padding: 24px;
  min-height: 300px;

  h3 {
    margin: 0 0 16px 0;
    color: #111827;
    font-size: 16px;
    font-weight: 600;
  }
}

.description-text {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  white-space: pre-line;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  margin: 0;
}

.code-block {
  background: #1f2937;
  color: #f9fafb;
  border-radius: 8px;
  padding: 16px;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  overflow-x: auto;

  &.result {
    background: #065f46;
    color: #d1fae5;
  }

  &.error {
    background: #991b1b;
    color: #fecaca;
  }

  &.debug {
    background: #1e40af;
    color: #dbeafe;
    font-size: 12px;
  }

  code {
    color: inherit;
    background: transparent;
  }
}

.debug-section {
  margin-bottom: 24px;

  h4 {
    margin: 0 0 12px 0;
    color: #374151;
    font-size: 14px;
    font-weight: 600;
    padding-bottom: 8px;
    border-bottom: 1px solid #e5e7eb;
  }
}

.artifact-full {
  text-align: center;

  .image-container {
    img {
      max-width: 100%;
      height: auto;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
  }

  .image-error {
    padding: 20px;
    color: #dc2626;
    text-align: center;

    .el-icon {
      font-size: 32px;
      margin-bottom: 12px;
    }

    span {
      display: block;
      font-size: 18px;
      font-weight: 500;
      margin-bottom: 16px;
    }

    .error-details {
      text-align: left;
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 8px;
      padding: 16px;
      margin-top: 16px;

      p {
        margin: 0 0 12px 0;
        font-weight: 600;
        color: #991b1b;
        font-size: 16px;
      }

      .debug-info {
        background: #1f2937;
        color: #f9fafb;
        padding: 12px;
        border-radius: 6px;
        font-size: 13px;
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
        text-align: left;
        overflow-x: auto;
        line-height: 1.4;
      }
    }
  }

  .image-loading {
    padding: 40px;
    color: #6b7280;
    text-align: center;

    .el-icon {
      font-size: 32px;
      margin-bottom: 12px;
      color: #d97706;
    }

    span {
      display: block;
      font-size: 16px;
    }
  }
}

.artifact-data {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e5e7eb;
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

/* 响应式设计 */
@media (max-width: 768px) {
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 0 auto;
  }

  .tab-content {
    padding: 16px;
  }

  .tool-main-content {
    padding: 16px;
  }
}
</style>
