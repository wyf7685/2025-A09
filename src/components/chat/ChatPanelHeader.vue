<script setup lang="ts">
import Model from '@/components/icons/Model.vue';
import { useSessionStore } from '@/stores/session';
import type { MLModel } from '@/types';
import { Document, DocumentAdd, Setting, Share } from '@element-plus/icons-vue';
import { ElButton, ElTooltip } from 'element-plus';
import { computed } from 'vue';

defineProps<{
  sessionModels: MLModel[];
}>();

const emit = defineEmits<{
  openModelSelectDialog: [];
  openModelConfigDialog: [];
  openSaveWorkflowDialog: [];
  openWorkflowManager: [];
  openReportDialog: [];
}>();

const sessionStore = useSessionStore();
const currentSessionName = computed(() => {
  return sessionStore.currentSession?.name || '未命名会话';
});

const openModelSelectDialog = () => emit('openModelSelectDialog');
const openModelConfigDialog = () => emit('openModelConfigDialog');
const openSaveWorkflowDialog = () => emit('openSaveWorkflowDialog');
const openWorkflowManager = () => emit('openWorkflowManager');
const openReportDialog = () => emit('openReportDialog');
</script>

<template>
  <div class="chat-panel-header">
    <div class="header-left">
      <!-- 会话标题 -->
      <el-tooltip :content="currentSessionName" placement="bottom">
        <span class="session-title">
          {{ currentSessionName }}
        </span>
      </el-tooltip>
    </div>
    <div class="header-right">
      <el-button @click="openModelSelectDialog" :icon="Model" class="panel-header-btn"
        :type="sessionModels.length ? 'primary' : 'default'">
        {{ sessionModels.length || 0 > 0 ? `已选择 ${sessionModels.length} 个模型` : '机器学习模型' }}
      </el-button>
      <el-button @click="openSaveWorkflowDialog" :icon="DocumentAdd" class="panel-header-btn">
        保存流程
      </el-button>
      <el-button @click="openWorkflowManager" :icon="Share" class="panel-header-btn">
        调用流程
      </el-button>
      <el-button @click="openReportDialog" :icon="Document" class="panel-header-btn">
        生成报告
      </el-button>
      <div class="action-divider"></div>
      <el-button @click="openModelConfigDialog" :icon="Setting" class="panel-header-btn" type="success" plain>
        模型配置
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.chat-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  /* 与 SessionSidebar 保持一致 */
  height: 56px;
  /* 与 SessionSidebar 保持一致 */
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
  background: #ffffff;

  .header-left {
    display: flex;
    align-items: center;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .session-title {
    font-weight: 600;
    margin-left: 12px;
    color: #1f2937;
    font-size: 16px;
    max-height: 1.2rem;
    overflow: hidden;
  }
}

.action-divider {
  display: inline-block;
  height: 20px;
  width: 1px;
  background-color: #dcdfe6;
  margin: 0 8px;
  vertical-align: middle;
}
</style>
