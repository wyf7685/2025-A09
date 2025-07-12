export type SourceID = string;

/**
 * 数据源元数据
 */
export interface DataSourceMetadata {
  id: string;
  name: string;
  source_type: string;
  created_at: string;
  description: string;
  row_count?: number;
  column_count?: number;
  columns?: string[];
  dtypes?: Record<string, string>;
}

export type DataSourceMetadataWithID = DataSourceMetadata & {
  source_id: SourceID;
};

/**
 * 数据源预览信息
 */
export interface DataSourcePreview {
  metadata: DataSourceMetadata;
  preview: Record<string, any>[];
}

/**
 * Dremio 数据源
 */
export interface DremioSource {
  path: string[] | string;
  type: string;
  id?: string;
  name?: string;
  description?: string;
}

/**
 * 数据库连接配置
 */
export interface DatabaseConnectionConfig {
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
}

/**
 * 数据库连接配置
 */
export interface DatabaseConfig {
  name: string;
  type: 'postgres' | 'mysql' | 'oracle' | 'sqlserver';
  connection: DatabaseConnectionConfig | any;
}
