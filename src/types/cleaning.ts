export type CleaningStep = 'upload' | 'analysis' | 'cleaning' | 'complete';

export interface DataQualityReport {
  is_valid: boolean;
  quality_score: number;
  total_rows?: number;
  total_columns?: number;
  issues: Array<{
    type: string;
    column?: string;
    count?: number;
    description: string;
  }>;
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
  column: string;
  type: string;
}

export interface CleaningAction {
  type: string;
  column?: string;
  parameters?: any;
}
