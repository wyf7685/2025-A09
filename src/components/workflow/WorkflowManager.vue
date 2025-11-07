<script setup lang="ts">
import { useWorkflowStore } from '@/stores/workflow';
import type { WorkflowDefinition } from '@/types/workflow';
import { InfoFilled, Refresh, VideoPlay } from '@element-plus/icons-vue';
import {
  ElAlert, ElButton, ElCard, ElCollapse, ElCollapseItem, ElDialog, ElDivider, ElEmpty,
  ElForm, ElFormItem, ElIcon, ElInput, ElMessage, ElMessageBox, ElOption, ElSelect, ElTag, ElTooltip
} from 'element-plus';
import { onMounted, ref, watch } from 'vue';

const visible = defineModel<boolean>('visible', { required: true });

// 组件属性
const props = defineProps<{
  selectionMode: boolean;
  sessionId: string;
  dataSources: { id: string; name: string; }[];
}>();

interface WorkflowExecutionPayload {
  workflow_id: string;
  workflow_name: string;
  session_id: string;
  datasource_mappings: Record<string, string>;
  message: string;
}

// 组件事件
const emit = defineEmits<{
  workflowExecuting: [payload: WorkflowExecutionPayload];
}>();

// 使用工作流存储
const workflowStore = useWorkflowStore();
const workflows = ref<WorkflowDefinition[]>([]);
const loading = ref(false);
const executing = ref(false);
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
  if (workflow.initial_datasets) {
    Object.keys(workflow.initial_datasets).forEach(sourceId => {
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

  // 验证数据源映射是否完整
  const requiredSourceIds = Object.keys(selectedWorkflow.value.initial_datasets || {});
  // const mappedSourceIds = Object.keys(dataSourceMappings.value);

  const missingMappings = requiredSourceIds.filter(id => !dataSourceMappings.value[id]);
  if (missingMappings.length > 0) {
    ElMessage.warning(`请为所有数据源提供映射: ${missingMappings.join(', ')}`);
    return;
  }

  executing.value = true;
  try {
    // 构造工作流执行的消息
    const workflowMessage = `执行工作流：${selectedWorkflow.value.name}`;

    // 关闭对话框
    visible.value = false;

    // 发出事件，让父组件通过聊天接口执行工作流
    emit('workflowExecuting', {
      workflow_id: selectedWorkflow.value.id,
      workflow_name: selectedWorkflow.value.name,
      session_id: props.sessionId,
      datasource_mappings: dataSourceMappings.value,
      message: workflowMessage,
    });

    ElMessage.success('开始执行工作流，请查看聊天界面');
  } catch (error) {
    console.error('执行工作流失败:', error);
    ElMessage.error('执行工作流失败');
  } finally {
    executing.value = false;
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
  visible.value = false;
  selectedWorkflow.value = null;
  detailDialogVisible.value = false;
};

// 打开创建工作流对话框
// const openCreateDialog = () => {
//   createDialogVisible.value = true;
//   newWorkflowForm.value = {
//     name: '',
//     description: '',
//   };
// };

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
watch(() => visible.value, (newVal) => {
  if (newVal) {
    loadWorkflows();
  }
});
</script>

<template>
  <el-dialog
    v-model="visible"
    title="工作流管理"
    width="800px"
    :before-close="handleClose"
    :close-on-click-modal="false">
    <div class="workflow-manager">
      <div class="header">
        <div class="actions">
          <el-button @click="loadWorkflows" :loading="loading">
            <el-icon>
              <Refresh />
            </el-icon>
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
    <el-dialog :model-value="detailDialogVisible" @update:model-value="detailDialogVisible = $event"
      :title="selectedWorkflow?.name || '工作流详情'" width="50%" @close="closeDialog">
      <div v-if="selectedWorkflow" class="workflow-detail">
        <p class="description">{{ selectedWorkflow.description || '无描述' }}</p>

        <div class="datasource-mappings" v-if="Object.keys(selectedWorkflow.initial_datasets || {}).length > 0">
          <h3>数据源映射 <el-tooltip content="工作流使用的数据源需要映射到当前会话的数据源才能执行"><el-icon>
                <InfoFilled />
              </el-icon></el-tooltip></h3>
          <el-alert type="info" show-icon :closable="false" title="提示：将工作流中使用的原始数据源映射到当前会话的数据源"
            style="margin-bottom: 15px;" />
          <div class="mapping-list">
            <div v-for="sourceId in Object.keys(selectedWorkflow.initial_datasets)" :key="sourceId"
              class="mapping-item">
              <div class="mapping-source">
                <span class="source-label">工作流数据源:</span>
                <span class="source-name">{{ selectedWorkflow.initial_datasets[sourceId] }}</span>
              </div>
              <el-divider direction="vertical" />
              <div class="mapping-target">
                <span class="source-label">映射到:</span>
                <el-select v-model="dataSourceMappings[sourceId]" placeholder="选择数据源" style="width: 220px;"
                  :class="{ 'required-mapping': !dataSourceMappings[sourceId] }">
                  <el-option v-for="ds in props.dataSources" :key="ds.id" :label="ds.name" :value="ds.id" />
                </el-select>
              </div>
            </div>
          </div>
        </div>

        <div class="tool-calls-list">
          <h3>工具调用流程 ({{ selectedWorkflow.tool_calls?.length || 0 }})</h3>
          <el-alert type="success" show-icon :closable="false" title="这些工具调用将按照原始顺序执行，但使用新的数据源映射"
            style="margin-bottom: 15px;" />
          <el-collapse>
            <el-collapse-item v-for="(toolCall, index) in selectedWorkflow.tool_calls || []" :key="index"
              :title="(index + 1) + '. ' + toolCall.name">
              <div class="tool-call-detail">
                <div class="tool-call-header">
                  <div class="tool-call-type">工具类型: <span class="tool-type">{{ toolCall.name }}</span></div>
                </div>
                <div class="tool-call-args">
                  <div class="args-header">参数:</div>
                  <el-card shadow="never" class="args-card">
                    <pre>{{ JSON.stringify(toolCall.args, null, 2) }}</pre>
                  </el-card>
                </div>
                <div class="tool-call-desc">
                  <el-tag size="small" effect="plain" type="info">
                    执行时会使用当前会话的数据源
                  </el-tag>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="closeDialog">取消</el-button>
          <el-button
            type="primary"
            @click="executeSelectedWorkflow"
            :disabled="Object.keys(selectedWorkflow?.initial_datasets || {}).some(id => !dataSourceMappings[id])"
            :loading="executing">
            <el-icon>
              <VideoPlay />
            </el-icon>
            执行工作流
          </el-button>
        </span>
      </template>
    </el-dialog>

  </el-dialog>

  <!-- 创建工作流对话框 -->
  <el-dialog :model-value="createDialogVisible" @update:model-value="createDialogVisible = $event" title="保存为工作流"
    width="40%">
    <el-form :model="newWorkflowForm" label-width="80px">
      <el-form-item label="名称" required>
        <el-input v-model="newWorkflowForm.name" placeholder="输入工作流名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="newWorkflowForm.description" type="textarea" :rows="3" placeholder="输入工作流描述（可选）" />
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
  align-items: center;
  padding: 10px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background-color: #f9fafc;
}

.mapping-source,
.mapping-target {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mapping-source {
  flex: 1;
  margin-right: 10px;
}

.mapping-target {
  flex: 2;
}

.source-label {
  color: #606266;
  font-size: 14px;
}

.source-name {
  font-weight: 500;
  color: #409eff;
  padding: 2px 8px;
  background: rgba(64, 158, 255, 0.1);
  border-radius: 4px;
}

.required-mapping {
  border-color: #f56c6c;
}

.tool-calls-list {
  margin-top: 20px;
}

.tool-call-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 5px;
}

.tool-call-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.tool-call-type {
  font-weight: 500;
}

.tool-type {
  color: #409eff;
  font-weight: 600;
}

.tool-call-args {
  margin-top: 10px;
}

.args-header {
  margin-bottom: 5px;
  font-weight: 500;
}

.args-card {
  background-color: #f9fafc;
}

.args-card pre {
  margin: 0;
  font-family: monospace;
  font-size: 14px;
  white-space: pre-wrap;
}

.tool-call-desc {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
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
