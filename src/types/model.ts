/**
 * 机器学习模型信息
 */
export interface Model {
  id: string;
  name: string;
  type: string;
  description?: string;
  created_at: string;
  last_used?: string;
  target_column: string;
  accuracy: number;
  score: number;
  features: string[];
  feature_count: number;
  dataset_id: string;
  session_id: string;
  status: string;
  version: string;
  metrics: Record<string, any>;
}

/**
 * LLM模型信息
 */
export interface LLMModel {
  id: string;
  name: string;
  provider: string;
  description?: string;
}

/**
 * 模型列表响应
 */
export interface ModelsResponse {
  models: Model[];
}
