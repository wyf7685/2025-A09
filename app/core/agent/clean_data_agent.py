"""
数据清洗专用 Agent
只进行数据规范性检测，提供清洗建议，不执行实际清洗
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from app.log import logger


class CleanDataAgent:
    """数据清洗 Agent - 专门用于数据规范性检测和清洗建议"""
    
    def __init__(self):
        self.name = "CleanDataAgent"
        self.description = "专门用于数据清洗的智能助手，提供数据规范性检测和清洗建议"
        
    def check_data_quality(self, file_path: str) -> Dict[str, Any]:
        """
        检测数据质量和规范性 - 只做基本的格式检查
        
        Args:
            file_path: CSV 文件路径
            
        Returns:
            检测结果包括：
            - is_valid: 是否符合基本规范
            - issues: 发现的问题列表
            - data_info: 数据基本信息
        """
        try:
            logger.info(f"开始检测文件: {file_path}")
            
            # 读取数据
            df = pd.read_csv(file_path)
              # 基本信息
            basic_info = {
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': df.columns.tolist(),
                'data_types': {col: str(df[col].dtype) for col in df.columns},
                'missing_values_total': int(df.isnull().sum().sum()),
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
            
            # 问题检测
            issues = []
            
            # 1. 检查列名规范性
            column_names = df.columns.tolist()
            for col in column_names:
                if ' ' in col or col != col.strip():
                    issues.append({
                        'type': 'column_name',
                        'column': col,
                        'description': f'列名 "{col}" 包含空格或前后有多余空白'
                    })
            
            # 2. 检查缺失值（简单统计）
            missing_info = df.isnull().sum()
            for col, count in missing_info.items():
                if count > 0:
                    issues.append({
                        'type': 'missing_values',
                        'column': col,
                        'count': int(count),
                        'description': f'列 "{col}" 有 {count} 个缺失值'
                    })
            
            # 3. 检查重复行
            duplicate_count = df.duplicated().sum()
            if duplicate_count > 0:
                issues.append({
                    'type': 'duplicates',
                    'count': int(duplicate_count),
                    'description': f'发现 {duplicate_count} 行重复数据'
                })
            
            # 4. 检查数据类型一致性（基本检查）
            for col in df.columns:
                if df[col].dtype == 'object':
                    # 检查文本列是否包含数字
                    non_null_values = df[col].dropna()
                    if len(non_null_values) > 0:
                        sample_values = non_null_values.head(10)
                        numeric_pattern_count = sum(1 for val in sample_values 
                                                   if str(val).replace('.', '').replace('-', '').isdigit())
                        if numeric_pattern_count > len(sample_values) * 0.8:
                            issues.append({
                                'type': 'data_type',
                                'column': col,
                                'current_type': 'text',
                                'suggested_type': 'numeric',
                                'description': f'列 "{col}" 可能应该是数值类型'
                            })
            
            # 计算质量分数（简单算法）
            quality_score = max(0, 100 - len(issues) * 10)
            is_valid = len(issues) == 0
            
            result = {
                'is_valid': is_valid,
                'quality_score': quality_score,
                'issues': issues,
                'data_info': basic_info
            }
            
            logger.info(f"检测完成: 发现 {len(issues)} 个问题，质量分数: {quality_score}")
            return result
            
        except Exception as e:
            logger.error(f"数据质量检测失败: {str(e)}")
            return {
                'is_valid': False,
                'quality_score': 0,
                'issues': [{'type': 'error', 'description': f'文件读取失败: {str(e)}'}],
                'data_info': {'rows': 0, 'columns': 0, 'column_names': [], 'data_types': {}, 'missing_values_total': 0, 'file_size': 0},
                'error': str(e)
            }
    
    def get_cleaning_suggestions(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        根据检测到的问题提供清洗建议（仅提供建议，不执行清洗）
        
        Args:
            issues: 检测到的问题列表
            
        Returns:
            清洗建议列表
        """
        suggestions = []
        
        for issue in issues:
            issue_type = issue.get('type')
            column = issue.get('column')
            
            if issue_type == 'column_name':
                suggestions.append({
                    'title': f'规范化列名 "{column}"',
                    'description': '列名包含空格或特殊字符，建议规范化',
                    'severity': 'low',
                    'column': column,
                    'type': issue_type,
                    'options': [
                        {'method': 'normalize', 'description': '自动规范化（移除空格、转换为下划线）'},
                        {'method': 'manual', 'description': '手动重命名'},
                        {'method': 'keep', 'description': '保持原样'}
                    ]
                })
            
            elif issue_type == 'missing_values':
                suggestions.append({
                    'title': f'处理 {column} 列的缺失值',
                    'description': f'发现 {issue.get("count", 0)} 个缺失值，需要处理',
                    'severity': 'high' if issue.get('count', 0) > 100 else 'medium',
                    'column': column,
                    'type': issue_type,
                    'options': [
                        {'method': 'drop', 'description': '删除含有缺失值的行'},
                        {'method': 'fill_mean', 'description': '用均值填充（适用于数值列）'},
                        {'method': 'fill_median', 'description': '用中位数填充（适用于数值列）'},
                        {'method': 'fill_mode', 'description': '用众数填充（适用于分类列）'}
                    ]
                })
            
            elif issue_type == 'duplicates':
                suggestions.append({
                    'title': '处理重复数据',
                    'description': f'发现 {issue.get("count", 0)} 行重复数据',
                    'severity': 'medium',
                    'column': 'all',
                    'type': issue_type,
                    'options': [
                        {'method': 'drop', 'description': '删除重复行'},
                        {'method': 'keep_first', 'description': '保留第一次出现的记录'},
                        {'method': 'keep_last', 'description': '保留最后一次出现的记录'},
                        {'method': 'manual', 'description': '手动处理'}
                    ]
                })
            
            elif issue_type == 'data_type':
                suggestions.append({
                    'title': f'转换 {column} 列的数据类型',
                    'description': f'当前是文本类型，建议转换为数值类型',
                    'severity': 'low',
                    'column': column,
                    'type': issue_type,
                    'options': [
                        {'method': 'to_numeric', 'description': '转换为数值类型'},
                        {'method': 'keep_string', 'description': '保持文本类型'},
                        {'method': 'manual', 'description': '手动检查后决定'}
                    ]
                })
        
        return suggestions
