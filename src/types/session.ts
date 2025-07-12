import type { ChatEntry } from './chat';

/**
 * 会话信息
 */
export interface Session {
  id: string;
  dataset_id: string;
  name: string | null;
  chat_history: ChatEntry[];
  created_at: string;
}

/**
 * 会话列表项
 */
export interface SessionListItem {
  id: string;
  name: string;
  created_at: string;
  chat_count: number;
}
