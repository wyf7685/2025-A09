/**
 * 机器学习模型信息
 */
export interface MLModel {
  id: string;
  name: string;
  type: string;
  description: string;
  created_at: string;
  last_used: string;
  target_column: string;
  features: string[];
  feature_count: number;
  dataset_id: string;
  session_id: string;
  session_name?: string;
  status: string;
  version: string;
  accuracy: number;
  score: number;
  metrics: Record<string, number>;
  hyperparams?: Record<string, any>;
  is_registered?: boolean;
}

/**
 * LLM模型信息
 */
export interface LLMModel {
  id: string;
  name: string;
  provider: string;
  description?: string;
  apiUrl?: string; // 自定义API URL
  apiKey?: string; // 自定义API Key
  available?: boolean; // 是否已配置可用
}

/**
 * 模型列表响应
 */
export interface ModelsResponse {
  models: MLModel[];
}
