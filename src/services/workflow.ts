import type { WorkflowDefinition, SaveWorkflowPayload, ExecuteWorkflowPayload } from '@/types/workflow';
import api from '@/utils/api';

/**
 * 工作流管理API服务
 */
class WorkflowService {
  /**
   * 获取所有工作流
   */
  async getWorkflows(): Promise<WorkflowDefinition[]> {
    const response = await api.get('/api/workflow');
    return response.data;
  }

  /**
   * 获取单个工作流
   */
  async getWorkflow(id: string): Promise<WorkflowDefinition> {
    const response = await api.get(`/api/workflow/${id}`);
    return response.data;
  }

  /**
   * 保存工作流
   */
  async saveWorkflow(payload: SaveWorkflowPayload): Promise<WorkflowDefinition> {
    const response = await api.post('/api/workflow', payload);
    return response.data;
  }

  /**
   * 执行工作流
   */
  async executeWorkflow(payload: ExecuteWorkflowPayload): Promise<{ success: boolean; session_id: string }> {
    const response = await api.post('/api/workflow/execute', payload);
    return response.data;
  }

  /**
   * 删除工作流
   */
  async deleteWorkflow(id: string): Promise<{ success: boolean }> {
    const response = await api.delete(`/api/workflow/${id}`);
    return response.data;
  }

  /**
   * 更新工作流
   */
  async updateWorkflow(id: string, updates: Partial<WorkflowDefinition>): Promise<WorkflowDefinition> {
    const response = await api.put(`/api/workflow/${id}`, updates);
    return response.data;
  }
}

export const workflowService = new WorkflowService();
