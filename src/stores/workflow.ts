import { defineStore } from 'pinia';
import { workflowService } from '@/services/workflow';
import type {
  ExecuteWorkflowPayload,
  SaveWorkflowPayload,
  WorkflowDefinition,
} from '@/types/workflow';

export const useWorkflowStore = defineStore('workflow', {
  state: () => ({
    workflowList: [] as WorkflowDefinition[],
    currentWorkflow: null as WorkflowDefinition | null,
    loading: false,
  }),

  actions: {
    /**
     * 获取所有工作流
     */
    async fetchWorkflows() {
      this.loading = true;
      try {
        this.workflowList = await workflowService.getWorkflows();
      } catch (error) {
        console.error('Failed to fetch workflows:', error);
        throw error;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 获取单个工作流
     */
    async getWorkflow(id: string) {
      try {
        return await workflowService.getWorkflow(id);
      } catch (error) {
        console.error(`Failed to get workflow ${id}:`, error);
        throw error;
      }
    },

    /**
     * 保存工作流
     */
    async saveWorkflow(payload: SaveWorkflowPayload) {
      try {
        const workflow = await workflowService.saveWorkflow(payload);
        // 如果当前列表中不包含这个工作流，则添加到列表
        if (!this.workflowList.some((wf) => wf.id === workflow.id)) {
          this.workflowList.push(workflow);
        }
        return workflow;
      } catch (error) {
        console.error('Failed to save workflow:', error);
        throw error;
      }
    },

    /**
     * 执行工作流
     */
    async executeWorkflow(payload: ExecuteWorkflowPayload) {
      try {
        return await workflowService.executeWorkflow(payload);
      } catch (error) {
        console.error('Failed to execute workflow:', error);
        throw error;
      }
    },

    /**
     * 删除工作流
     */
    async deleteWorkflow(id: string) {
      try {
        const result = await workflowService.deleteWorkflow(id);
        if (result) {
          // 从列表中移除已删除的工作流
          this.workflowList = this.workflowList.filter((wf) => wf.id !== id);
        }
        return result;
      } catch (error) {
        console.error(`Failed to delete workflow ${id}:`, error);
        throw error;
      }
    },
  },
});
