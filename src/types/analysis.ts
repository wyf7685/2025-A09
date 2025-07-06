/**
 * 分析结果
 */
export interface AnalysisResult {
  id?: string;
  timestamp: string;
  type?: string;
  report: string;
  figures?: Figure[];
  dataset_shape: [number, number]; // [行数, 列数]
}

/**
 * 图表数据
 */
export interface Figure {
  data: string;
  title?: string;
}

/**
 * 分析报告
 */
export interface AnalysisReport {
  id?: string;
  timestamp: string;
  type?: string;
  report: string;
  figures?: Figure[];
  dataset_shape: [number, number]; // [行数, 列数]
}
