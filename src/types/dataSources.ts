/**
 * 数据源信息
 */
export interface DataSource {
  name: string;
  type: string;
  description?: string;
  status: 'connected' | 'disconnected';
}

/**
 * 数据源配置表单数据
 */
export interface ConfigFormData {
  name: string;
  type: string;
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
}

/**
 * 数据集响应
 */
export interface DatasetResponse {
  dataset_id: string;
  overview?: {
    shape: [number, number];
    columns: string[];
    head: Record<string, any>[];
  };
}
