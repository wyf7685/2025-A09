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
  dataset_name?: string;
  dataset_description?: string;
  session_id: string;
  session_name?: string;
  status: string;
  version: string;
  accuracy: number;
  metrics: Record<string, number>;
  hyperparams?: Record<string, any>;
  is_registered?: boolean;
}

/**
 * LLM模型信息（不包含敏感信息如API Key）
 */
export interface LLMModel {
  id: string;
  name: string;
  provider: string;
  apiUrl?: string; // 自定义API URL
  model_name?: string; // 用户自定义的显示名称
  api_model_name?: string; // API调用时使用的正确模型名称
  available?: boolean; // 是否已配置可用
}

/**
 * 模型列表响应
 */
export interface ModelsResponse {
  models: MLModel[];
}
