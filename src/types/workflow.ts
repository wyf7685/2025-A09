import type { ToolCall } from '@/types/chat';

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  tool_calls: ToolCall[];
  initial_datasets: Record<string, string>; // 初始数据集名称 -> 描述
}

export interface WorkflowExecutionOptions {
  datasource_mappings: Record<string, string>; // 工作流数据源ID -> 实际会话数据源ID的映射
}

export interface SaveWorkflowPayload {
  name: string;
  description: string;
  session_id: string;
}

export interface ExecuteWorkflowPayload {
  workflow_id: string;
  session_id: string;
  datasource_mappings: Record<string, string>;
}
