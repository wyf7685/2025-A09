<script setup lang="ts">
import { useSessionStore } from '@/stores/session';
import type { AgentModelConfig } from '@/types';
import api from '@/utils/api';
import { ChatDotRound, Cpu, Document, EditPen, Setting } from '@element-plus/icons-vue';
import { ElButton, ElCard, ElDialog, ElForm, ElFormItem, ElIcon, ElMessage, ElOption, ElSelect } from 'element-plus';
import { onMounted, ref, watch } from 'vue';

const visible = defineModel<boolean>('visible', { required: true });

const sessionStore = useSessionStore();
const loading = ref(false);
const availableModels = ref<Array<{ id: string; name: string; }>>([]);

// 表单数据
const formData = ref<AgentModelConfig>({
  default: '',
  chat: '',
  create_title: '',
  summary: '',
  code_generation: '',
});

// 节点配置项
const nodeConfigs = [
  {
    key: 'default' as keyof AgentModelConfig,
    label: '默认模型',
    description: '作为其他节点的后备模型，未明确配置时使用此模型',
    icon: Setting,
    color: '#409EFF',
  },
  {
    key: 'chat' as keyof AgentModelConfig,
    label: '对话生成',
    description: '负责理解用户意图并生成自然流畅的对话响应',
    icon: ChatDotRound,
    color: '#67C23A',
  },
  {
    key: 'code_generation' as keyof AgentModelConfig,
    label: '代码生成',
    description: '生成和优化代码，提供技术实现方案',
    icon: Cpu,
    color: '#F56C6C',
  },
  {
    key: 'create_title' as keyof AgentModelConfig,
    label: '标题生成',
    description: '自动为会话创建简洁准确的标题',
    icon: EditPen,
    color: '#E6A23C',
  },
  {
    key: 'summary' as keyof AgentModelConfig,
    label: '内容摘要',
    description: '提取关键信息生成对话摘要和分析总结',
    icon: Document,
    color: '#909399',
  },

];

// 加载可用模型列表
const loadAvailableModels = async () => {
  try {
    const response = await api.get<{ models: Array<{ id: string; name: string; provider: string; }>; }>(
      '/models/available'
    );
    availableModels.value = response.data.models.map(m => ({
      id: m.id,
      name: `${m.name} (${m.provider})`,
    }));
  } catch (error) {
    console.error('加载模型列表失败:', error);
    ElMessage.error('加载模型列表失败');
  }
};

// 当对话框打开时，加载当前配置
watch(visible, async (newVal) => {
  if (newVal) {
    loading.value = true;
    try {
      await loadAvailableModels();

      // 加载当前会话的模型配置
      if (sessionStore.currentSession?.agent_model_config) {
        formData.value = { ...sessionStore.currentSession.agent_model_config };
      }
    } finally {
      loading.value = false;
    }
  }
});

// 保存配置
const saveConfig = async () => {
  if (!formData.value.default) {
    ElMessage.warning('请至少选择默认模型');
    return;
  }

  loading.value = true;
  try {
    await sessionStore.updateSessionAgentModelConfig({
      default: formData.value.default,
      chat: formData.value.chat || undefined,
      create_title: formData.value.create_title || undefined,
      summary: formData.value.summary || undefined,
      code_generation: formData.value.code_generation || undefined,
    });

    ElMessage.success('模型配置已保存');
    visible.value = false;
  } catch (error) {
    console.error('保存模型配置失败:', error);
    ElMessage.error('保存模型配置失败');
  } finally {
    loading.value = false;
  }
};

// 重置为默认模型
const resetToDefault = (key: keyof AgentModelConfig) => {
  if (key !== 'default') {
    formData.value[key] = '';
  }
};

// 快速设置所有节点为同一模型
const setAllToDefault = () => {
  if (!formData.value.default) {
    ElMessage.warning('请先选择默认模型');
    return;
  }

  formData.value.chat = formData.value.default;
  formData.value.create_title = formData.value.default;
  formData.value.summary = formData.value.default;
  formData.value.code_generation = formData.value.default;

  ElMessage.success('已将所有节点设置为默认模型');
};

onMounted(() => {
  if (visible.value) {
    loadAvailableModels();
  }
});
</script>

<template>
  <el-dialog
    v-model="visible"
    width="800px"
    :close-on-click-modal="false"
    class="agent-model-config-dialog">
    <template #header>
      <div class="dialog-title">
        <el-icon class="title-icon">
          <Setting />
        </el-icon>
        <span>Agent 模型配置</span>
      </div>
    </template>

    <div class="dialog-content" v-loading="loading">
      <!-- 顶部说明 -->
      <div class="content-header">
        <p class="header-desc">
          为不同的 Agent 节点配置专用模型，优化各场景下的性能表现
        </p>
        <el-button size="small" @click="setAllToDefault" plain>
          全部使用默认模型
        </el-button>
      </div>

      <!-- 配置卡片列表 -->
      <el-form :model="formData" label-position="top">
        <div class="config-grid">
          <el-card v-for="config in nodeConfigs" :key="config.key" class="config-card"
            :class="{ 'is-required': config.key === 'default' }" shadow="hover">
            <div class="card-header">
              <div class="header-left">
                <el-icon :color="config.color" :size="20" class="node-icon">
                  <component :is="config.icon" />
                </el-icon>
                <div class="title-wrapper">
                  <span class="node-title">{{ config.label }}</span>
                  <span class="required-badge" v-if="config.key === 'default'">必填</span>
                </div>
              </div>
              <el-button v-if="config.key !== 'default' && formData[config.key]" text size="small"
                @click="resetToDefault(config.key)" class="reset-btn">
                重置
              </el-button>
            </div>

            <p class="node-desc">{{ config.description }}</p>

            <el-form-item class="model-selector">
              <el-select v-model="formData[config.key]" placeholder="选择模型" filterable
                :clearable="config.key !== 'default'"
                size="large">
                <el-option v-for="model in availableModels" :key="model.id" :label="model.name" :value="model.id" />
              </el-select>
            </el-form-item>
          </el-card>
        </div>
      </el-form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false" size="large">取消</el-button>
        <el-button type="primary" @click="saveConfig" :loading="loading" size="large">
          保存配置
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.agent-model-config-dialog {
  :deep(.el-dialog__header) {
    padding: 20px 24px;
    border-bottom: 1px solid #e5e7eb;
    margin-right: 0;
  }

  :deep(.el-dialog__body) {
    padding: 24px;
  }

  :deep(.el-dialog__footer) {
    padding: 16px 24px;
    border-top: 1px solid #e5e7eb;
  }

  .dialog-title {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 18px;
    font-weight: 600;
    color: #1f2937;

    .title-icon {
      font-size: 22px;
      color: #409EFF;
    }
  }

  .dialog-content {
    max-height: calc(80vh - 200px);
    overflow-y: auto;
    padding-right: 4px;

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-track {
      background: #f5f5f5;
      border-radius: 3px;
    }

    &::-webkit-scrollbar-thumb {
      background: #d1d5db;
      border-radius: 3px;
      transition: background 0.2s;
    }

    &::-webkit-scrollbar-thumb:hover {
      background: #9ca3af;
    }
  }

  .content-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 16px 20px;
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border-radius: 12px;
    border: 1px solid #bae6fd;

    .header-desc {
      margin: 0;
      font-size: 14px;
      color: #0c4a6e;
      line-height: 1.6;
      flex: 1;
      padding-right: 16px;
    }
  }

  .config-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;

    @media (max-width: 900px) {
      grid-template-columns: 1fr;
    }
  }

  .config-card {
    border-radius: 12px;
    transition: all 0.3s ease;

    &.is-required {
      border: 2px solid #409EFF;
      background: linear-gradient(135deg, #f0f9ff 0%, #ffffff 100%);
    }

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
    }

    :deep(.el-card__body) {
      padding: 20px;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;

      .header-left {
        display: flex;
        align-items: center;
        gap: 12px;
        flex: 1;

        .node-icon {
          flex-shrink: 0;
        }

        .title-wrapper {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;

          .node-title {
            font-size: 16px;
            font-weight: 600;
            color: #1f2937;
          }

          .required-badge {
            padding: 2px 8px;
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            font-size: 11px;
            font-weight: 500;
            border-radius: 12px;
            letter-spacing: 0.5px;
          }
        }
      }

      .reset-btn {
        color: #6b7280;
        padding: 4px 8px;
        font-size: 12px;

        &:hover {
          color: #3b82f6;
          background: #eff6ff;
        }
      }
    }

    .node-desc {
      margin: 0 0 16px 0;
      font-size: 13px;
      color: #6b7280;
      line-height: 1.6;
      min-height: 42px;
    }

    .model-selector {
      margin-bottom: 0;

      :deep(.el-form-item__content) {
        margin: 0 !important;
      }

      :deep(.el-select) {
        width: 100%;
      }

      :deep(.el-input__wrapper) {
        border-radius: 8px;
        transition: all 0.3s ease;

        &:hover {
          box-shadow: 0 0 0 1px #409EFF inset;
        }
      }
    }
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;

    .el-button {
      min-width: 100px;
      border-radius: 8px;
      font-weight: 500;
    }
  }
}
</style>
