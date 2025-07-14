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

// 数据库类型定义
export type DremioDatabaseType = 'MSSQL' | 'MYSQL' | 'ORACLE' | 'POSTGRES';

// 基础数据库连接接口
interface BaseDatabaseConnection {
  hostname: string;
  port: number;
  username: string;
  password: string;
}

// MSSQL 连接接口
export interface MSSQLConnection extends BaseDatabaseConnection {}

// MySQL 连接接口
export interface MySQLConnection extends BaseDatabaseConnection {}

// PostgreSQL 连接接口
export interface PostgreSQLConnection extends BaseDatabaseConnection {
  databaseName: string;
}

// Oracle 连接接口
export interface OracleConnection extends BaseDatabaseConnection {
  instance: string;
}

// 任意数据库连接类型
export type AnyDatabaseConnection =
  | MSSQLConnection
  | MySQLConnection
  | PostgreSQLConnection
  | OracleConnection;
