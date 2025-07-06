/**
 * 机器学习模型信息
 */
export interface Model {
  id: string;
  name: string;
  type: string;
  created_at: string;
  target: string;
  score: number;
  features: string[];
  dataset_id: string;
  session_id: string;
}

/**
 * 模型列表响应
 */
export interface ModelsResponse {
  models: Model[];
}
