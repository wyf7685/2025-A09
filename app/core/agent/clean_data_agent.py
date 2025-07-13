"""
数据清洗专用 Agent
只进行数据规范性检测，提供清洗建议，不执行实际清洗
"""

# ruff: noqa: PD002

from pathlib import Path
from typing import Any

import pandas as pd

from app.log import logger


class CleanDataAgent:
    """数据清洗 Agent - 专门用于数据规范性检测和清洗建议"""

    def check_data_quality(self, file_path: Path) -> dict[str, Any]:
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
        issues = []
        logger.info(f"开始检测文件: {file_path}")
        try:
            # 读取数据
            df = pd.read_csv(file_path)
            # 基本信息
            basic_info = {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": df.columns.tolist(),
                "data_types": {col: str(df[col].dtype) for col in df.columns},
                "missing_values_total": int(df.isna().sum().sum()),
                "file_size": file_path.stat().st_size if file_path.exists() else 0,
            }

            # 1. 检查列名规范性
            issues.extend(
                {"type": "column_name", "column": col, "description": f'列名 "{col}" 包含空格或前后有多余空白'}
                for col in df.columns.tolist()
                if " " in col or col != col.strip()
            )

            # 2. 检查缺失值（简单统计）
            issues.extend(
                {
                    "type": "missing_values",
                    "column": col,
                    "count": int(count),
                    "description": f'列 "{col}" 有 {count} 个缺失值',
                }
                for col, count in df.isa().sum().items()
                if count > 0
            )

            # 3. 检查重复行
            if (duplicate_count := df.duplicated().sum()) > 0:
                issues.append(
                    {
                        "type": "duplicates",
                        "count": int(duplicate_count),
                        "description": f"发现 {duplicate_count} 行重复数据",
                    }
                )

            # 4. 检查数据类型一致性（基本检查）
            for col in df.columns:
                if df[col].dtype == "object":
                    # 检查文本列是否包含数字
                    non_null_values = df[col].dropna()
                    if len(non_null_values) > 0:
                        sample_values = non_null_values.head(10)
                        numeric_pattern_count = sum(
                            1 for val in sample_values if str(val).replace(".", "").replace("-", "").isdigit()
                        )
                        if numeric_pattern_count > len(sample_values) * 0.8:
                            issues.append(
                                {
                                    "type": "data_type",
                                    "column": col,
                                    "current_type": "text",
                                    "suggested_type": "numeric",
                                    "description": f'列 "{col}" 可能应该是数值类型',
                                }
                            )

            # 计算质量分数（简单算法）
            quality_score = max(0, 100 - len(issues) * 10)
            is_valid = len(issues) == 0

            result = {"is_valid": is_valid, "quality_score": quality_score, "issues": issues, "data_info": basic_info}

            logger.info(f"检测完成: 发现 {len(issues)} 个问题，质量分数: {quality_score}")
            return result

        except Exception as e:
            logger.error(f"数据质量检测失败: {e}")
            return {
                "is_valid": False,
                "quality_score": 0,
                "issues": [{"type": "error", "description": f"文件读取失败: {e}"}],
                "data_info": {
                    "rows": 0,
                    "columns": 0,
                    "column_names": [],
                    "data_types": {},
                    "missing_values_total": 0,
                    "file_size": 0,
                },
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
