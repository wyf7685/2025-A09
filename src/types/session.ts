import type { ChatEntry } from './chat';

export interface AgentModelConfig {
  default: string;
  chat: string;
  create_title: string;
  summary: string;
  code_generation: string;
}

/**
 * 会话信息
 */
export interface Session {
  id: string;
  dataset_ids: string[];
  mcp_ids: string[] | null;
  model_ids: string[] | null;
  name: string | null;
  chat_history: ChatEntry[];
  created_at: string;
  agent_model_config: AgentModelConfig;
}

/**
 * 会话列表项
 */
export interface SessionListItem {
  id: string;
  name: string | null;
  created_at: string;
  chat_count: number;
}
