import type { ChatEntry } from './chat';
import type { AnalysisResult } from './analysis';

/**
 * 会话信息
 */
export interface Session {
  id: string;
  name?: string; // 会话名称，使用用户第一次提问内容
  created_at?: string; // 创建时间
  current_dataset?: string;
  chat_history: ChatEntry[];
  analysis_results: AnalysisResult[];
  dataset_loaded?: boolean; // 是否已加载数据集
  chat_count?: number; // 对话数量
  analysis_count?: number; // 分析结果数量
}
