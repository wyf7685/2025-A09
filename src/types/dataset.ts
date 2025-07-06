/**
 * 数据集信息
 */
export interface Dataset {
  id: string;
  name: string;
  source_type: string;
  file_name?: string;
  created_at: string;
  columns?: string[];
  row_count?: number;
  overview?: DatasetOverview;
}

/**
 * 数据集概览信息
 */
export interface DatasetOverview {
  shape: [number, number]; // [行数, 列数]
  columns: string[];
  dtypes: Record<string, string>;
  missing_values: Record<string, number>;
  head: Record<string, any>[];
}

/**
 * 列信息
 */
export interface ColumnInfo {
  name: string;
  dtype: string;
  missing: number;
}

/**
 * 上传结果
 */
export interface UploadResult {
  dataset_id: string;
  session_id: string;
  overview: DatasetOverview;
}

/**
 * 上传文件项
 */
export interface FileItem {
  name: string;
  size: number;
  type: string;
  raw: File;
}
