<script setup lang="ts">
import { useModelStore } from '@/stores/model';
import { useSessionStore } from '@/stores/session';
import type { MLModel } from '@/types';
import { ElButton, ElCollapse, ElCollapseItem, ElDialog, ElEmpty, ElSkeleton, ElTabPane, ElTabs } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';
import ModelList from './ModelList.vue';

const props = defineProps<{
  currentSessionId: string;
}>();

const emit = defineEmits<{
  'models-updated': [];
}>();

// 使用v-model绑定已选模型列表
const selectedModels = defineModel<MLModel[]>('sessionModels', { required: true });
const visible = defineModel<boolean>('visible', { required: true });

// 本地状态
const loading = ref(false);
const models = ref<MLModel[]>([]);
const selectedModelIds = ref<string[]>([]);

// 按会话分组的模型
const modelsBySession = computed(() => {
  const sessions: Record<string, { id: string, name: string, models: MLModel[]; }> = {};

  for (const model of models.value) {
    if (!model.session_id) continue;

    if (!sessions[model.session_id]) {
      sessions[model.session_id] = {
        id: model.session_id,
        name: model.session_name || '无名会话',
        models: []
      };
    }

    sessions[model.session_id].models.push(model);
  }

  return Object.values(sessions);
});

// 按类型分组的模型
const modelsByType = computed(() => {
  const types: Record<string, MLModel[]> = {};

  for (const model of models.value) {
    const type = model.type || '未知类型';
    if (!types[type]) {
      types[type] = [];
    }
    types[type].push(model);
  }

  return types;
});

// 会话store
const sessionStore = useSessionStore();
const modelStore = useModelStore();

// 加载所有可用模型
const loadModels = async () => {
  // 通过API获取所有模型
  const allModels = (await modelStore.getAllModels()).models;

  // 排除当前会话的模型
  models.value = allModels.filter(model => {
    return model.session_id !== props.currentSessionId;
  });
};

// 切换模型选择状态
const toggleModel = (modelId: string) => {
  const index = selectedModelIds.value.indexOf(modelId);
  if (index === -1) {
    selectedModelIds.value.push(modelId);
  } else {
    selectedModelIds.value.splice(index, 1);
  }
};

// 确认选择
const confirmSelection = async () => {
  try {
    // 通过API将选中的模型关联到当前会话
    await sessionStore.updateSessionModels(props.currentSessionId, selectedModelIds.value);

    // 从API重新获取更新的模型列表
    const models = await sessionStore.getSessionModels(props.currentSessionId);
    selectedModels.value = models;

    // 通知父组件模型已更新
    emit('models-updated');

    // 关闭对话框
    visible.value = false;
  } catch (error) {
    console.error('更新会话模型失败:', error);
  }
};

// 初始加载已选模型
onMounted(async () => {
  // 初始化已选模型ID列表(在加载前先设置)
  selectedModelIds.value = selectedModels.value?.map(m => m.id) || [];

  loading.value = true;

  try {
    // 加载所有可用模型,排除当前会话的模型
    await loadModels();
  } catch (error) {
    console.error('加载模型失败:', error);
  } finally {
    loading.value = false;
  }
});

// 监听对话框可见性变化，重置已选模型ID列表
watch(() => visible.value, () => {
  selectedModelIds.value = selectedModels.value?.map(m => m.id) || [];
});
</script>

<template>
  <el-dialog
    v-model="visible"
    title="选择模型"
    width="60%"
    top="5vh"
    :destroy-on-close="true">
    <div class="model-selector-content">
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="!models.length" class="no-models">
        <el-empty description="暂无可用模型" />
        <p class="hint">
          在其他数据分析会话中训练并保存的模型将显示在这里
        </p>
      </div>

      <el-tabs v-else type="border-card">
        <el-tab-pane label="所有模型">
          <model-list
            :models="models"
            :selected-models="selectedModelIds"
            @select="toggleModel" />
        </el-tab-pane>

        <el-tab-pane label="按会话分组">
          <el-collapse accordion>
            <el-collapse-item
              v-for="session in modelsBySession"
              :key="session.id"
              :title="`${session.name || '无名会话'} (${session.models.length}个模型)`">
              <model-list
                :models="session.models"
                :selected-models="selectedModelIds"
                @select="toggleModel" />
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <el-tab-pane label="按类型分组">
          <el-collapse accordion>
            <el-collapse-item
              v-for="(models, type) in modelsByType"
              :key="type"
              :title="`${type} (${models.length}个模型)`">
              <model-list
                :models="models"
                :selected-models="selectedModelIds"
                @select="toggleModel" />
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="confirmSelection">
          确认选择 ({{ selectedModelIds.length }})
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
.model-selector-content {
  min-height: 300px;
  max-height: 60vh;
  overflow-y: auto;
}

.loading-container {
  padding: 20px;
}

.no-models {
  text-align: center;
  padding: 20px;
}

.hint {
  color: #909399;
  font-size: 14px;
  margin-top: 10px;
}
</style>
