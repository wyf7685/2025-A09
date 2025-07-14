"""
数据清洗专用 Agent
只进行数据规范性检测，提供清洗建议，不执行实际清洗
"""

# ruff: noqa: PD002

import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.log import logger


class CleanDataAgent:
    """数据清洗 Agent - 专门用于数据规范性检测和清洗建议"""

    def __init__(self):
        self.name = "CleanDataAgent"
        self.description = "专门用于数据清洗的智能助手，提供数据规范性检测和清洗建议"
        
        # 支持的文件格式
        self.supported_formats = {'.csv', '.xlsx', '.xls'}
        
        # 常见的数据类型模式
        self.patterns = {
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'phone': re.compile(r'^[\+]?[1-9]?\d{1,14}$'),
            'date': re.compile(r'^\d{4}-\d{2}-\d{2}$'),
            'time': re.compile(r'^\d{2}:\d{2}:\d{2}$'),
            'url': re.compile(r'^https?://[^\s/$.?#].[^\s]*$'),
            'numeric': re.compile(r'^-?\d+\.?\d*$')
        }

    def check_data_quality(self, file_path: Path) -> dict[str, Any]:
        """
        检测数据质量和规范性 - 全面的格式和内容检查

        Args:
            file_path: 数据文件路径 (支持 CSV, Excel)

        Returns:
            检测结果包括：
            - is_valid: 是否符合基本规范
            - quality_score: 质量评分 (0-100)
            - issues: 发现的问题列表
            - data_info: 数据基本信息
            - suggestions_count: 建议数量
        """
        issues = []
        logger.info(f"开始检测文件: {file_path} (格式: {file_path.suffix})")
        try:
            # 检查文件格式
            if file_path.suffix.lower() not in self.supported_formats:
                raise ValueError(f"不支持的文件格式: {file_path.suffix}")
            
            # 读取数据
            df = self._read_file(file_path)
            
            if df.empty:
                raise ValueError("文件为空或无法读取数据")
              # 基本信息
            basic_info = {
                "rows": int(len(df)),
                "columns": int(len(df.columns)),
                "column_names": df.columns.tolist(),
                "data_types": {col: str(df[col].dtype) for col in df.columns},
                "missing_values_total": int(df.isna().sum().sum()),
                "file_size": int(file_path.stat().st_size if file_path.exists() else 0),
                "file_format": str(file_path.suffix.lower()),
                "memory_usage": int(df.memory_usage(deep=True).sum())
            }

            # 1. 检查列名规范性
            issues.extend(self._check_column_names(df))

            # 2. 检查缺失值（简单统计）
            issues.extend(self._check_missing_values(df))

            # 3. 检查重复行
            issues.extend(self._check_duplicates(df))

            # 4. 检查数据类型一致性（基本检查）
            issues.extend(self._check_data_types(df))

            # 5. 检查数据格式规范性（邮箱、日期）
            issues.extend(self._check_data_formats(df))

            # 6. 检查异常值
            issues.extend(self._check_outliers(df))

            # 7. 检查数据完整性
            issues.extend(self._check_data_integrity(df))            # 计算质量分数
            quality_score = float(self._calculate_quality_score(issues, len(df), len(df.columns)))
            is_valid = bool(quality_score >= 80)  # 80分以上认为是高质量数据

            result = {
                "is_valid": is_valid,
                "quality_score": quality_score,
                "issues": issues,
                "data_info": basic_info,
                "suggestions_count": int(len(issues))
            }

            logger.info(f"检测完成: 发现 {len(issues)} 个问题，质量分数: {quality_score}")
            return result
        
        except Exception as e:
            logger.error(f"数据质量检测失败: {e}")
            return {
                "is_valid": False,
                "quality_score": 0.0,
                "issues": [{"type": "error", "description": f"文件读取失败: {e}"}],
                "data_info": {
                    "rows": 0,
                    "columns": 0,
                    "column_names": [],
                    "data_types": {},
                    "missing_values_total": 0,
                    "file_size": int(file_path.stat().st_size if file_path.exists() else 0),
                    "file_format": str(file_path.suffix.lower() if file_path.exists() else "unknown"),
                    "memory_usage": 0
                },
                "suggestions_count": 1,
                "error": str(e),
            }

    def get_cleaning_suggestions(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        根据检测到的问题提供清洗建议（仅提供建议，不执行清洗）

        Args:
            issues: 检测到的问题列表

        Returns:
            清洗建议列表
        """
        suggestions = []

        for issue in issues:
            issue_type = issue.get("type")
            column = issue.get("column")

            if issue_type == "column_name":
                suggestions.append(
                    {
                        "title": f'规范化列名 "{column}"',
                        "description": "列名包含空格或特殊字符，建议规范化",
                        "severity": "low",
                        "column": column,
                        "type": issue_type,
                        "options": [
                            {"method": "normalize", "description": "自动规范化（移除空格、转换为下划线）"},
                            {"method": "manual", "description": "手动重命名"},
                            {"method": "keep", "description": "保持原样"},
                        ],
                    }
                )

            elif issue_type == "missing_values":
                suggestions.append(
                    {
                        "title": f"处理 {column} 列的缺失值",
                        "description": f"发现 {issue.get('count', 0)} 个缺失值，需要处理",
                        "severity": "high" if issue.get("count", 0) > 100 else "medium",
                        "column": column,
                        "type": issue_type,
                        "options": [
                            {"method": "drop", "description": "删除含有缺失值的行"},
                            {"method": "fill_mean", "description": "用均值填充（适用于数值列）"},
                            {"method": "fill_median", "description": "用中位数填充（适用于数值列）"},
                            {"method": "fill_mode", "description": "用众数填充（适用于分类列）"},
                        ],
                    }
                )

            elif issue_type == "duplicates":
                suggestions.append(
                    {
                        "title": "处理重复数据",
                        "description": f"发现 {issue.get('count', 0)} 行重复数据",
                        "severity": "medium",
                        "column": "all",
                        "type": issue_type,
                        "options": [
                            {"method": "drop", "description": "删除重复行"},
                            {"method": "keep_first", "description": "保留第一次出现的记录"},
                            {"method": "keep_last", "description": "保留最后一次出现的记录"},
                            {"method": "manual", "description": "手动处理"},
                        ],
                    }
                )

            elif issue_type == "data_type":
                suggestions.append(
                    {
                        "title": f"转换 {column} 列的数据类型",
                        "description": "当前是文本类型，建议转换为数值类型",
                        "severity": "low",
                        "column": column,
                        "type": issue_type,
                        "options": [
                            {"method": "to_numeric", "description": "转换为数值类型"},
                            {"method": "keep_string", "description": "保持文本类型"},
                            {"method": "manual", "description": "手动检查后决定"},
                        ],
                    }
                )

        return suggestions

    def apply_cleaning_action(self, df: pd.DataFrame, file_path: Path, action: dict[str, Any]) -> dict[str, Any]:
        logger.info(f"开始应用清洗动作到文件: {file_path}")

        try:
            method = action.get("method")
            column = action.get("column")

            if not method or not column:
                logger.warning(f"跳过无效的清洗动作: {action}")
                return {"status": "error", "message": "无效的清洗动作"}

            if method == "normalize" and column in df.columns:
                df.rename(columns={column: column.strip().replace(" ", "_")}, inplace=True)

            elif method == "drop" and column in df.columns:
                df.dropna(subset=[column], inplace=True)

            elif method == "fill_mean" and column in df.columns and pd.api.types.is_numeric_dtype(df[column]):
                df[column].fillna(df[column].mean(), inplace=True)

            elif method == "fill_median" and column in df.columns and pd.api.types.is_numeric_dtype(df[column]):
                df[column].fillna(df[column].median(), inplace=True)

            elif method == "fill_mode" and column in df.columns:
                mode_value = df[column].mode().iloc[0]
                df[column].fillna(mode_value, inplace=True)

            elif method == "drop_duplicates":
                df.drop_duplicates(inplace=True)

            elif method == "to_numeric" and column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

            return {"status": "success", "action": action}
        except Exception as e:
            logger.error(f"应用清洗动作失败: {e}")
            return {"status": "error", "message": str(e)}

    def _read_file(self, file_path: Path) -> pd.DataFrame:
        """
        根据文件扩展名读取文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            pandas DataFrame
        """
        file_extension = file_path.suffix.lower()
        
        if file_extension == '.csv':
            # 尝试不同的编码格式读取CSV
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            for encoding in encodings:
                try:
                    return pd.read_csv(file_path, encoding=encoding)
                except UnicodeDecodeError:
                    continue
            # 如果所有编码都失败，使用默认编码
            return pd.read_csv(file_path)
            
        elif file_extension in {'.xlsx', '.xls'}:
            return pd.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_extension}")

    def _check_column_names(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查列名规范性"""
        issues = []
        for col in df.columns:
            # 检查空格和前后空白
            if " " in col or col != col.strip():
                issues.append({
                    "type": "column_name",
                    "column": col,
                    "description": f'列名 "{col}" 包含空格或前后有多余空白'
                })
            
            # 检查特殊字符
            if re.search(r'[^\w\s_-]', col):
                issues.append({
                    "type": "column_name",
                    "column": col,
                    "description": f'列名 "{col}" 包含特殊字符，建议使用字母、数字、下划线'
                })
            
            # 检查是否为空或重复
            if col == '' or col.isspace():
                issues.append({
                    "type": "column_name",
                    "column": col,
                    "description": "发现空列名"
                })
                
        # 检查重复列名
        duplicated_cols = df.columns[df.columns.duplicated()].tolist()
        for col in duplicated_cols:
            issues.append({
                "type": "column_name",
                "column": col,
                "description": f'列名 "{col}" 重复出现'
            })
            
        return issues

    def _check_missing_values(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查缺失值"""
        issues = []
        missing_counts = df.isna().sum()
        
        for col, count in missing_counts.items():
            if count > 0:
                missing_percentage = (count / len(df)) * 100
                severity = "high" if missing_percentage > 50 else "medium" if missing_percentage > 20 else "low"
                
                issues.append({
                    "type": "missing_values",
                    "column": col,
                    "count": int(count),
                    "percentage": round(missing_percentage, 2),
                    "severity": severity,
                    "description": f'列 "{col}" 有 {count} 个缺失值 ({missing_percentage:.1f}%)'
                })
        return issues

    def _check_duplicates(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查重复行"""
        issues = []
        duplicate_count = df.duplicated().sum()
        
        if duplicate_count > 0:
            duplicate_percentage = (duplicate_count / len(df)) * 100
            severity = "high" if duplicate_percentage > 10 else "medium"
            
            issues.append({
                "type": "duplicates",
                "count": int(duplicate_count),
                "percentage": round(duplicate_percentage, 2),
                "severity": severity,
                "description": f"发现 {duplicate_count} 行重复数据 ({duplicate_percentage:.1f}%)"
            })
        return issues

    def _check_data_types(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查数据类型一致性"""
        issues = []
        
        for col in df.columns:
            if df[col].dtype == "object":
                # 检查文本列是否应该是数值
                non_null_values = df[col].dropna()
                if len(non_null_values) > 0:
                    sample_values = non_null_values.head(50)
                    numeric_pattern_count = sum(
                        1 for val in sample_values 
                        if self.patterns['numeric'].match(str(val).strip())
                    )
                    
                    if numeric_pattern_count > len(sample_values) * 0.8:
                        issues.append({
                            "type": "data_type",
                            "column": col,
                            "current_type": "text",
                            "suggested_type": "numeric",
                            "confidence": round((numeric_pattern_count / len(sample_values)) * 100, 1),
                            "description": f'列 "{col}" 可能应该是数值类型'
                        })
        return issues

    def _check_data_formats(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查数据格式规范性"""
        issues = []
        
        for col in df.columns:
            if df[col].dtype == "object":
                non_null_values = df[col].dropna().astype(str)
                if len(non_null_values) == 0:
                    continue
                
                sample_values = non_null_values.head(20)
                
                # 检查邮箱格式
                if any('email' in col.lower() or '@' in str(val) for val in sample_values):
                    invalid_emails = [
                        val for val in sample_values 
                        if '@' in str(val) and not self.patterns['email'].match(str(val))
                    ]
                    if invalid_emails:
                        issues.append({
                            "type": "data_format",
                            "column": col,
                            "format_type": "email",
                            "invalid_count": len(invalid_emails),
                            "description": f'列 "{col}" 包含 {len(invalid_emails)} 个格式不正确的邮箱'
                        })
                
                # 检查日期格式
                if any('date' in col.lower() or 'time' in col.lower() for _ in [col]):
                    # 尝试解析日期
                    try:
                        pd.to_datetime(sample_values, errors='coerce')
                    except:
                        issues.append({
                            "type": "data_format",
                            "column": col,
                            "format_type": "date",
                            "description": f'列 "{col}" 的日期格式可能不一致'
                        })
        
        return issues

    def _check_outliers(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查异常值"""
        issues = []
        
        numeric_columns = df.select_dtypes(include=['number']).columns
        
        for col in numeric_columns:
            if df[col].notna().sum() < 3:  # 需要至少3个值才能检测异常值
                continue
                
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            if IQR == 0:  # 避免除零错误
                continue
                
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)][col]
            
            if len(outliers) > 0:
                outlier_percentage = (len(outliers) / len(df)) * 100
                severity = "high" if outlier_percentage > 5 else "medium" if outlier_percentage > 1 else "low"
                
                issues.append({
                    "type": "outliers",
                    "column": col,
                    "count": len(outliers),
                    "percentage": round(outlier_percentage, 2),
                    "severity": severity,
                    "range": f"[{lower_bound:.2f}, {upper_bound:.2f}]",
                    "description": f'列 "{col}" 发现 {len(outliers)} 个异常值 ({outlier_percentage:.1f}%)'
                })
        
        return issues

    def _check_data_integrity(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """检查数据完整性"""
        issues = []
        
        # 检查空行
        empty_rows = df.isnull().all(axis=1).sum()
        if empty_rows > 0:
            issues.append({
                "type": "data_integrity",
                "subtype": "empty_rows",
                "count": int(empty_rows),
                "description": f"发现 {empty_rows} 行完全为空的数据"
            })
        
        # 检查数据一致性（同一列中数据长度差异很大）
        for col in df.select_dtypes(include=['object']).columns:
            non_null_values = df[col].dropna().astype(str)
            if len(non_null_values) > 0:
                lengths = non_null_values.str.len()
                if lengths.std() > lengths.mean():  # 标准差大于平均值表示长度差异很大
                    issues.append({
                        "type": "data_integrity",
                        "subtype": "inconsistent_length",
                        "column": col,
                        "avg_length": round(lengths.mean(), 1),
                        "std_length": round(lengths.std(), 1),
                        "description": f'列 "{col}" 中数据长度差异较大，可能存在格式不一致'
                    })
        
        return issues

    def _calculate_quality_score(self, issues: list[dict[str, Any]], rows: int, columns: int) -> float:
        """计算质量分数"""
        base_score = 100.0
        
        # 根据问题类型和严重程度扣分
        for issue in issues:
            issue_type = issue.get("type", "")
            severity = issue.get("severity", "medium")
            
            # 基础扣分
            if issue_type == "error":
                base_score -= 50
            elif issue_type == "missing_values":
                percentage = issue.get("percentage", 0)
                base_score -= min(percentage / 2, 20)  # 最多扣20分
            elif issue_type == "duplicates":
                percentage = issue.get("percentage", 0)
                base_score -= min(percentage, 15)  # 最多扣15分
            elif issue_type == "column_name":
                base_score -= 5
            elif issue_type == "data_type":
                base_score -= 3
            elif issue_type == "data_format":
                base_score -= 8
            elif issue_type == "outliers":
                if severity == "high":
                    base_score -= 10
                elif severity == "medium":
                    base_score -= 5
                else:
                    base_score -= 2
            elif issue_type == "data_integrity":
                base_score -= 7
            else:
                base_score -= 3
        
        # 确保分数在0-100范围内
        return max(0.0, min(100.0, base_score))
