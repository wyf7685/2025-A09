import type { ChatEntry } from './chat';
import type { AnalysisResult } from './analysis';

/**
 * 会话信息
 */
export interface Session {
  id: string;
  current_dataset?: string;
  chat_history: ChatEntry[];
  analysis_results: AnalysisResult[];
}
