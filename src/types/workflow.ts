import type { ToolCall } from '@/types/chat';

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  tool_calls: ToolCall[];
  initial_datasets: Record<string, string>; // 初始数据集名称列表
}

export interface WorkflowExecutionOptions {
  datasource_mappings: Record<string, string>; // 工作流数据源ID -> 实际会话数据源ID的映射
}

export interface SaveWorkflowPayload {
  name: string;
  description: string;
  messages: any[]; // 包含工具调用的消息列表
  session_id: string;
}

export interface ExecuteWorkflowPayload {
  workflow_id: string;
  session_id: string;
  datasource_mappings: Record<string, string>;
}
