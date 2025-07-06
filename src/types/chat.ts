import type { Figure } from "./analysis";

/**
 * 聊天条目
 */
export interface ChatEntry {
  id: string;
  timestamp: string;
  role: 'user' | 'assistant';
  content: string;
  user_message?: string;
  assistant_response?: string;
  execution_results?: ExecutionResult[];
}

/**
 * 执行结果
 */
export interface ExecutionResult {
  query: string;
  output?: string;
  figure?: Figure;
}

/**
 * 聊天消息
 */
export interface ChatMessage {
  type: 'user' | 'assistant';
  content: string;
  timestamp: string;
  execution_results?: ExecutionResult[];
  charts?: Figure[];
}
