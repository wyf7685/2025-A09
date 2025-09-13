<script setup lang="ts">
import { ref, onMounted, computed, watch, type PropType } from 'vue';
import { useWorkflowStore } from '@/stores/workflow';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue';
import type { WorkflowDefinition, WorkflowExecutionOptions } from '@/types/workflow';

// 组件属性
const props = defineProps({
  // 是否显示对话框
  visible: {
    type: Boolean,
    default: false,
  },
  // 如果为true，表示处于选择模式，用于选择一个工作流执行
  selectionMode: {
    type: Boolean,
    default: false,
  },
  // 会话ID
  sessionId: {
    type: String,
    default: '',
  },
  // 数据源列表
  dataSources: {
    type: Array as PropType<{ id: string; name: string }[]>,
    default: () => [],
  },
});

// 组件事件
const emit = defineEmits(['update:visible', 'workflowSelected', 'workflowExecuted', 'cancel']);

// 计算属性：用于v-model绑定
const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
});

// 使用工作流存储
const workflowStore = useWorkflowStore();
const workflows = ref<WorkflowDefinition[]>([]);
const loading = ref(false);
const createDialogVisible = ref(false);

// 选中的工作流
const selectedWorkflow = ref<WorkflowDefinition | null>(null);

// 数据源映射
const dataSourceMappings = ref<Record<string, string>>({});

// 新工作流表单
const newWorkflowForm = ref({
  name: '',
  description: '',
});

// 加载所有工作流
const loadWorkflows = async () => {
  loading.value = true;
  try {
    await workflowStore.fetchWorkflows();
    workflows.value = workflowStore.workflowList;
  } catch (error) {
    console.error('加载工作流失败:', error);
    ElMessage.error('加载工作流失败');
  } finally {
    loading.value = false;
  }
};

// 选择工作流
const selectWorkflow = (workflow: WorkflowDefinition) => {
  selectedWorkflow.value = workflow;

  // 初始化数据源映射
  dataSourceMappings.value = {};

  // 如果工作流有数据源映射，为每个数据源提供默认值
  if (workflow.datasource_mappings) {
    Object.keys(workflow.datasource_mappings).forEach(sourceId => {
      if (props.dataSources && props.dataSources.length > 0) {
        // 默认映射到第一个可用的数据源
        dataSourceMappings.value[sourceId] = props.dataSources[0].id;
      }
    });
  }

  detailDialogVisible.value = true;
};

// 执行所选工作流
const executeSelectedWorkflow = async () => {
  if (!selectedWorkflow.value) {
    ElMessage.warning('请先选择一个工作流');
    return;
  }

  if (!props.sessionId) {
    ElMessage.warning('当前没有活跃的会话');
    return;
  }

  try {
    const result = await workflowStore.executeWorkflow({
      workflow_id: selectedWorkflow.value.id,
      session_id: props.sessionId,
      datasource_mappings: dataSourceMappings.value,
    });

    if (result) {
      ElMessage.success('工作流执行成功');
      emit('workflowExecuted', result);
      dialogVisible.value = false;
    }
  } catch (error) {
    console.error('执行工作流失败:', error);
    ElMessage.error('执行工作流失败');
  }
};

// 删除工作流
const deleteWorkflowItem = async (workflow: WorkflowDefinition) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除工作流 "${workflow.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    const result = await workflowStore.deleteWorkflow(workflow.id);
    if (result) {
      ElMessage.success('工作流删除成功');
      loadWorkflows();
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除工作流失败:', error);
      ElMessage.error('删除工作流失败');
    }
  }
};

// 关闭详情对话框
const closeDialog = () => {
  detailDialogVisible.value = false;
  selectedWorkflow.value = null;
};

// 处理对话框关闭
const handleClose = () => {
  emit('update:visible', false);
  selectedWorkflow.value = null;
  detailDialogVisible.value = false;
};

// 打开创建工作流对话框
const openCreateDialog = () => {
  createDialogVisible.value = true;
  newWorkflowForm.value = {
    name: '',
    description: '',
  };
};

// 保存当前会话为工作流
const saveCurrentConversationAsWorkflow = async () => {
  if (!props.sessionId) {
    ElMessage.warning('当前没有活跃的会话');
    return;
  }

  if (!newWorkflowForm.value.name.trim()) {
    ElMessage.warning('请输入工作流名称');
    return;
  }

  try {
    // 这里需要通过API获取当前会话的工具调用信息
    const result = await workflowStore.saveWorkflow({
      name: newWorkflowForm.value.name,
      description: newWorkflowForm.value.description,
      session_id: props.sessionId,
      messages: [], // 后端会获取会话的消息列表
    });

    if (result) {
      ElMessage.success('工作流保存成功');
      createDialogVisible.value = false;
      loadWorkflows();
    }
  } catch (error) {
    console.error('保存工作流失败:', error);
    ElMessage.error('保存工作流失败');
  }
};

// 内部对话框可见性
const detailDialogVisible = ref(false);

// 组件挂载时加载工作流
onMounted(() => {
  loadWorkflows();
});

// 监听visible属性变化
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadWorkflows();
  }
});
</script>

<template>
  <el-dialog
    :model-value="dialogVisible"
    @update:model-value="$emit('update:visible', $event)"
    title="工作流管理"
    width="800px"
    :before-close="handleClose"
    :close-on-click-modal="false"
  >
    <div class="workflow-manager">
      <div class="header">
        <div class="actions">
          <el-button @click="loadWorkflows" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>

      <div class="workflow-list" v-loading="loading">
        <template v-if="workflows.length > 0">
          <el-card v-for="workflow in workflows" :key="workflow.id" class="workflow-card">
            <template #header>
              <div class="workflow-card-header">
                <span class="workflow-name">{{ workflow.name }}</span>
                <div class="workflow-actions">
                  <el-button type="primary" size="small" @click="selectWorkflow(workflow)">
                    {{ props.selectionMode ? '选择' : '执行' }}
                  </el-button>
                  <el-button type="danger" size="small" @click="deleteWorkflowItem(workflow)">
                    删除
                  </el-button>
                </div>
              </div>
            </template>
            <div class="workflow-info">
              <p class="description">{{ workflow.description || '无描述' }}</p>
              <div class="metadata">
                <span class="created-at">创建时间: {{ new Date(workflow.created_at).toLocaleString() }}</span>
                <span v-if="workflow.updated_at !== workflow.created_at" class="updated-at">
                  更新时间: {{ new Date(workflow.updated_at).toLocaleString() }}
                </span>
              </div>
              <div class="tool-count">
                工具调用: {{ workflow.tool_calls?.length || 0 }}
              </div>
            </div>
          </el-card>
        </template>
        <el-empty v-else description="暂无工作流" />
      </div>
    </div>

    <!-- 工作流详情对话框 -->
    <el-dialog
      :model-value="detailDialogVisible"
      @update:model-value="detailDialogVisible = $event"
      :title="selectedWorkflow?.name || '工作流详情'"
      width="50%"
      @close="closeDialog"
    >
      <div v-if="selectedWorkflow" class="workflow-detail">
        <p class="description">{{ selectedWorkflow.description || '无描述' }}</p>

        <div class="datasource-mappings" v-if="Object.keys(selectedWorkflow.datasource_mappings || {}).length > 0">
          <h3>数据源映射</h3>
          <div class="mapping-list">
            <div v-for="(sourceDesc, sourceId) in selectedWorkflow.datasource_mappings" :key="sourceId" class="mapping-item">
              <span class="source-name">{{ sourceDesc }}</span>
              <el-select v-model="dataSourceMappings[sourceId]" placeholder="选择数据源">
                <el-option
                  v-for="ds in props.dataSources"
                  :key="ds.id"
                  :label="ds.name"
                  :value="ds.id"
                />
              </el-select>
            </div>
          </div>
        </div>

        <div class="tool-calls-list">
          <h3>工具调用 ({{ selectedWorkflow.tool_calls?.length || 0 }})</h3>
          <el-table :data="selectedWorkflow.tool_calls || []" style="width: 100%">
            <el-table-column prop="name" label="工具名称" width="180" />
            <el-table-column prop="args" label="参数">
              <template #default="scope">
                <pre>{{ JSON.stringify(scope.row.args, null, 2) }}</pre>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="closeDialog">取消</el-button>
          <el-button type="primary" @click="executeSelectedWorkflow">
            执行工作流
          </el-button>
        </span>
      </template>
    </el-dialog>

  </el-dialog>

  <!-- 创建工作流对话框 -->
  <el-dialog
    :model-value="createDialogVisible"
    @update:model-value="createDialogVisible = $event"
    title="保存为工作流"
    width="40%"
  >
    <el-form :model="newWorkflowForm" label-width="80px">
      <el-form-item label="名称" required>
        <el-input v-model="newWorkflowForm.name" placeholder="输入工作流名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input
          v-model="newWorkflowForm.description"
          type="textarea"
          :rows="3"
          placeholder="输入工作流描述（可选）"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCurrentConversationAsWorkflow">
          保存
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
.workflow-manager {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  gap: 10px;
}

.workflow-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.workflow-card {
  transition: all 0.3s;
}

.workflow-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.workflow-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.workflow-name {
  font-weight: bold;
  font-size: 16px;
}

.workflow-actions {
  display: flex;
  gap: 8px;
}

.workflow-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.description {
  color: #666;
  margin-bottom: 8px;
}

.metadata {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  color: #999;
}

.tool-count {
  font-size: 14px;
  color: #409eff;
  margin-top: 8px;
}

.datasource-mappings {
  margin: 20px 0;
}

.mapping-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-top: 10px;
}

.mapping-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.source-name {
  font-weight: 500;
}

.tool-calls-list {
  margin-top: 20px;
}

pre {
  white-space: pre-wrap;
  font-size: 12px;
  background-color: #f8f8f8;
  padding: 8px;
  border-radius: 4px;
  max-height: 120px;
  overflow-y: auto;
}
</style>
