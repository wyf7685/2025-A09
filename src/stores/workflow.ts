import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { workflowService } from '@/services/workflow';
import type { WorkflowDefinition, SaveWorkflowPayload, ExecuteWorkflowPayload } from '@/types/workflow';
import { ElMessage } from 'element-plus';

export const useWorkflowStore = defineStore('workflow', () => {
  // 状态
  const workflows = ref<WorkflowDefinition[]>([]);
  const loading = ref(false);
  const currentWorkflow = ref<WorkflowDefinition | null>(null);

  // 获取计算属性
  const workflowList = computed(() => workflows.value);
  const isLoading = computed(() => loading.value);

  // 获取所有工作流
  const fetchWorkflows = async () => {
    loading.value = true;
    try {
      workflows.value = await workflowService.getWorkflows();
    } catch (error) {
      console.error('获取工作流失败:', error);
      ElMessage.error('获取工作流列表失败');
    } finally {
      loading.value = false;
    }
  };

  // 获取单个工作流
  const fetchWorkflow = async (id: string) => {
    loading.value = true;
    try {
      currentWorkflow.value = await workflowService.getWorkflow(id);
      return currentWorkflow.value;
    } catch (error) {
      console.error(`获取工作流 ${id} 失败:`, error);
      ElMessage.error('获取工作流详情失败');
      return null;
    } finally {
      loading.value = false;
    }
  };

  // 保存工作流
  const saveWorkflow = async (payload: SaveWorkflowPayload) => {
    loading.value = true;
    try {
      const newWorkflow = await workflowService.saveWorkflow(payload);
      workflows.value.push(newWorkflow);
      ElMessage.success('工作流保存成功');
      return newWorkflow;
    } catch (error) {
      console.error('保存工作流失败:', error);
      ElMessage.error('保存工作流失败');
      return null;
    } finally {
      loading.value = false;
    }
  };

  // 执行工作流
  const executeWorkflow = async (payload: ExecuteWorkflowPayload) => {
    loading.value = true;
    try {
      const result = await workflowService.executeWorkflow(payload);
      ElMessage.success('工作流执行成功');
      return result;
    } catch (error) {
      console.error('执行工作流失败:', error);
      ElMessage.error('执行工作流失败');
      return null;
    } finally {
      loading.value = false;
    }
  };

  // 删除工作流
  const deleteWorkflow = async (id: string) => {
    loading.value = true;
    try {
      await workflowService.deleteWorkflow(id);
      workflows.value = workflows.value.filter(wf => wf.id !== id);
      ElMessage.success('工作流删除成功');
      return true;
    } catch (error) {
      console.error('删除工作流失败:', error);
      ElMessage.error('删除工作流失败');
      return false;
    } finally {
      loading.value = false;
    }
  };

  // 更新工作流
  const updateWorkflow = async (id: string, updates: Partial<WorkflowDefinition>) => {
    loading.value = true;
    try {
      const updated = await workflowService.updateWorkflow(id, updates);

      // 更新本地状态
      const index = workflows.value.findIndex(wf => wf.id === id);
      if (index !== -1) {
        workflows.value[index] = updated;
      }

      if (currentWorkflow.value?.id === id) {
        currentWorkflow.value = updated;
      }

      ElMessage.success('工作流更新成功');
      return updated;
    } catch (error) {
      console.error('更新工作流失败:', error);
      ElMessage.error('更新工作流失败');
      return null;
    } finally {
      loading.value = false;
    }
  };

  return {
    workflows,
    loading,
    currentWorkflow,
    workflowList,
    isLoading,
    fetchWorkflows,
    fetchWorkflow,
    saveWorkflow,
    executeWorkflow,
    deleteWorkflow,
    updateWorkflow,
  };
});
