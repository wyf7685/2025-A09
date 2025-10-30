export type CleaningStep = 'upload' | 'analysis' | 'cleaning' | 'complete';

export interface DataQualityReport {
  overall_score: number;
  total_rows: number;
  total_columns: number;
  missing_values_count: number;
  duplicate_rows_count: number;
  issues: Array<{
    type: string;
    column?: string;
    count?: number;
    description: string;
  }>;
  recommendations: string[];
  data_info: {
    rows: number;
    columns: number;
    column_names: string[];
    data_types: {
      [column: string]: string;
    };
    missing_values_total: number;
    file_size: number;
  };
}

export interface CleaningSuggestion {
  title: string;
  description: string;
  options: Array<{
    method: string;
    description: string;
  }>;
  severity: string;
  priority?: string;
  impact?: string;
  reason?: string;
  // 支持多列合并
  column: string;
  columns?: string[];
  type: string;
}

export interface CleaningAction {
  type: string;
  column?: string;
  parameters?: any;
}

export interface AnalyzeDataQualitySuccess {
  file_info: {
    file_id: string;
    original_filename: string;
    user_filename: string;
    description: string;
    upload_time: string;
    file_size: number;
  };
  success: true;
  quality_report: DataQualityReport;
  field_mappings: Record<string, string>;
  cleaning_suggestions: CleaningSuggestion[];
  summary: string;
  field_mappings_applied: boolean;
  cleaned_file_id: string | null;
}

export type AnalyzeDataQualityState = AnalyzeDataQualitySuccess & {
  data_uploaded?: boolean;
};

interface AnalyzeDataQualityError {
  success: false;
  error: string;
}

export type AnalyzeDataQualityResponse = AnalyzeDataQualitySuccess | AnalyzeDataQualityError;
