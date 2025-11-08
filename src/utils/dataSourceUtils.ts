/**
 * 数据源工具函数
 */

import type { DataSourceMetadataWithID } from '@/types';

/**
 * 格式化文件大小
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

/**
 * 格式化行数
 */
export const formatRowCount = (count: number | null | undefined): string => {
  if (!count) return 'N/A';

  if (count < 1000) return count.toString();
  if (count < 1000000) return (count / 1000).toFixed(1) + 'K';
  if (count < 1000000000) return (count / 1000000).toFixed(1) + 'M';

  return (count / 1000000000).toFixed(1) + 'B';
};

/**
 * 获取数据源类型图标
 */
export const getDataSourceIcon = (source: DataSourceMetadataWithID): string => {
  const type = source.source_type;

  if (type.includes('csv')) return 'document-copy';
  if (type.includes('excel') || type.includes('xlsx')) return 'document';
  if (type.includes('database') || type.includes('DIRECT')) return 'database';
  if (type.includes('json')) return 'document-copy';

  return 'folder';
};

/**
 * 获取数据源状态
 */
export const getDataSourceStatus = (
  source: DataSourceMetadataWithID,
): {
  status: 'active' | 'inactive' | 'error';
  text: string;
} => {
  // 这里可以根据实际情况判断数据源状态
  // 例如检查最后访问时间、连接状态等

  if (source.row_count && source.row_count > 0) {
    return { status: 'active', text: '正常' };
  }

  if (source.row_count === 0) {
    return { status: 'inactive', text: '无数据' };
  }

  return { status: 'error', text: '未知' };
};

/**
 * 生成数据源摘要
 */
export const generateDataSourceSummary = (source: DataSourceMetadataWithID): string => {
  const parts = [];

  if (source.row_count) {
    parts.push(`${formatRowCount(source.row_count)} 行`);
  }

  if (source.column_count) {
    parts.push(`${source.column_count} 列`);
  }

  return parts.join(' • ') || '无统计信息';
};

/**
 * 验证数据源名称
 */
export const validateDataSourceName = (
  name: string,
): {
  valid: boolean;
  message?: string;
} => {
  if (!name || name.trim().length === 0) {
    return { valid: false, message: '数据源名称不能为空' };
  }

  if (name.length > 100) {
    return { valid: false, message: '数据源名称不能超过100个字符' };
  }

  // 检查特殊字符
  const invalidChars = /[<>:"/\\|?*]/;
  if (invalidChars.test(name)) {
    return { valid: false, message: '数据源名称不能包含特殊字符 < > : " / \\ | ? *' };
  }

  return { valid: true };
};

/**
 * 导出数据源配置
 */
export const exportDataSourceConfig = (sources: DataSourceMetadataWithID[]): string => {
  const config = {
    version: '1.0',
    timestamp: new Date().toISOString(),
    sources: sources.map((source) => ({
      id: source.source_id,
      name: source.name,
      description: source.description,
      type: source.source_type,
      metadata: {
        row_count: source.row_count,
        column_count: source.column_count,
        created_at: source.created_at,
      },
    })),
  };

  return JSON.stringify(config, null, 2);
};

/**
 * 搜索数据源
 */
export const searchDataSources = (
  sources: DataSourceMetadataWithID[],
  query: string,
  options: {
    searchName?: boolean;
    searchDescription?: boolean;
    searchType?: boolean;
  } = {},
): DataSourceMetadataWithID[] => {
  const { searchName = true, searchDescription = true, searchType = false } = options;

  if (!query.trim()) return sources;

  const searchTerm = query.toLowerCase();

  return sources.filter((source) => {
    const matchName = searchName && source.name.toLowerCase().includes(searchTerm);
    const matchDescription =
      searchDescription && source.description?.toLowerCase().includes(searchTerm);
    const matchType = searchType && source.source_type.toLowerCase().includes(searchTerm);

    return matchName || matchDescription || matchType;
  });
};

/**
 * 排序数据源
 */
export const sortDataSources = (
  sources: DataSourceMetadataWithID[],
  sortBy: 'name' | 'type' | 'created_at' | 'row_count',
  order: 'asc' | 'desc' = 'asc',
): DataSourceMetadataWithID[] => {
  return [...sources].sort((a, b) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let aValue: any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let bValue: any;

    switch (sortBy) {
      case 'name':
        aValue = a.name.toLowerCase();
        bValue = b.name.toLowerCase();
        break;
      case 'type':
        aValue = a.source_type.toLowerCase();
        bValue = b.source_type.toLowerCase();
        break;
      case 'created_at':
        aValue = new Date(a.created_at || 0).getTime();
        bValue = new Date(b.created_at || 0).getTime();
        break;
      case 'row_count':
        aValue = a.row_count || 0;
        bValue = b.row_count || 0;
        break;
      default:
        return 0;
    }

    if (aValue < bValue) return order === 'asc' ? -1 : 1;
    if (aValue > bValue) return order === 'asc' ? 1 : -1;
    return 0;
  });
};
