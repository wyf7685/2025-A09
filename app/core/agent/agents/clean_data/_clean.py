import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.chain import get_llm
from app.log import logger

from .schemas import CleaningState


def _apply_single_cleaning(df: pd.DataFrame, suggestion: dict[str, Any]) -> pd.DataFrame:
    """应用单个清洗操作"""
    try:
        column: str = suggestion["column"]
        issue_type: str = suggestion["issue_type"]
        parameters: dict = suggestion.get("parameters", {})

        if issue_type == "duplicate_rows":
            return df.drop_duplicates(keep=parameters.get("keep", "first"))

        if issue_type == "column_name" and column in df.columns:
            # 规范化列名
            new_name = column.strip().replace(" ", "_")
            return df.rename(columns={column: new_name})

        if issue_type == "missing_values" and column in df.columns:
            method = parameters.get("method", "mean")
            if method == "mean" and df[column].dtype in ["int64", "float64"]:
                df[column] = df[column].fillna(df[column].mean())
            elif method == "mode":
                df[column] = df[column].fillna(df[column].mode().iloc[0])
            elif method == "drop":
                df = df.dropna(subset=[column])

            return df

        if issue_type == "data_type" and column in df.columns:
            target_type = parameters.get("target_type")
            if target_type == "numeric":
                df[column] = pd.to_numeric(df[column], errors="coerce")

            return df

        return df

    except Exception as e:
        logger.error(f"应用清洗操作失败: {e}")
        return df


def apply_cleaning(state: CleaningState) -> CleaningState:
    """应用清洗操作"""
    try:
        df_data = state["df_data"]
        suggestions = state["cleaning_suggestions"]

        if df_data is None:
            raise ValueError("数据未加载")

        df = pd.DataFrame(df_data)  # 反序列化DataFrame

        logger.info("开始应用清洗操作")

        # 创建数据副本用于清洗
        cleaned_df = df.copy()

        # 应用清洗建议
        for suggestion in suggestions:
            if suggestion.get("auto_apply", False):
                cleaned_df = _apply_single_cleaning(cleaned_df, suggestion)

        state["cleaned_df_data"] = cleaned_df.to_dict()  # 序列化清洗后DataFrame
        logger.info(f"清洗操作完成，处理了 {len(suggestions)} 个建议")
        return state

    except Exception as e:
        logger.error(f"应用清洗操作失败: {e}")
        state["error_message"] = str(e)
        return state


def _apply_single_cleaning_enhanced(df: pd.DataFrame, cleaning_params: dict[str, Any]) -> pd.DataFrame:
    """
    增强的单个清洗操作应用方法

    Args:
        df: 数据框
        cleaning_params: 清洗参数

    Returns:
        清洗后的数据框
    """
    try:
        column = cleaning_params.get("column")
        issue_type = cleaning_params.get("issue_type")
        parameters = cleaning_params.get("parameters", {})
        method = cleaning_params.get("method")

        logger.debug(f"应用清洗操作: {issue_type}, 列: {column}, 参数: {parameters}")

        if issue_type == "duplicate_rows":
            # 删除重复行
            keep = parameters.get("keep", "first")
            return df.drop_duplicates(keep=keep)

        if issue_type == "column_name" and column and column in df.columns:
            # 规范化列名（这个在字段映射阶段已经处理了，这里可以跳过）
            return df

        if issue_type == "missing_values" and column and column in df.columns:
            # 处理缺失值
            fill_method = method or parameters.get("method", "drop")

            if fill_method == "drop":
                # 删除含缺失值的行
                return df.dropna(subset=[column])
            if fill_method == "mean" and df[column].dtype in ["int64", "float64", "int32", "float32"]:
                # 用均值填充
                df[column] = df[column].fillna(df[column].mean())
                return df
            if fill_method == "median" and df[column].dtype in ["int64", "float64", "int32", "float32"]:
                # 用中位数填充
                df[column] = df[column].fillna(df[column].median())
                return df
            if fill_method == "mode":
                # 用众数填充
                mode_value = df[column].mode()
                if len(mode_value) > 0:
                    df[column] = df[column].fillna(mode_value.iloc[0])
                return df
            if fill_method == "forward":
                # 前向填充
                df[column] = df[column].ffill()
                return df
            if fill_method == "backward":
                # 后向填充
                df[column] = df[column].bfill()
                return df

            # 默认用众数填充
            mode_value = df[column].mode()
            if len(mode_value) > 0:
                df.loc[:, column] = df[column].fillna(mode_value.iloc[0])
            return df

        if issue_type == "data_type" and column and column in df.columns:
            # 数据类型转换
            target_type = parameters.get("target_type", "string")

            if target_type == "numeric":
                df[column] = pd.to_numeric(df[column], errors="coerce")
            elif target_type == "datetime":
                df[column] = pd.to_datetime(df[column], errors="coerce")
            elif target_type == "string":
                df[column] = df[column].astype(str)
            elif target_type == "category":
                df[column] = df[column].astype("category")

            return df

        if issue_type == "outliers" and column and column in df.columns:
            # 处理异常值
            treatment = method or parameters.get("treatment", "remove")

            if df[column].dtype in ["int64", "float64", "int32", "float32"]:
                Q1 = df[column].quantile(0.25)
                Q3 = df[column].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                if treatment == "remove":
                    # 删除异常值
                    mask = (df[column] >= lower_bound) & (df[column] <= upper_bound)
                    return df.loc[mask].copy()
                if treatment == "cap":
                    # 限制异常值
                    df.loc[:, column] = df[column].clip(lower_bound, upper_bound)
                    return df
                if treatment == "median":
                    # 用中位数替换异常值
                    median_value = df[column].median()
                    df.loc[(df[column] < lower_bound) | (df[column] > upper_bound), column] = median_value
                    return df

            return df

        logger.warning(f"未知的清洗操作类型: {issue_type}")
        return df

    except Exception as e:
        logger.error(f"应用单个清洗操作失败: {e}")
        return df


def apply_cleaning_actions(path: Path, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """应用指定的清洗动作"""
    try:
        # 加载数据
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(path)
        else:
            raise ValueError(f"不支持的文件格式: {path.suffix}")

        # 应用清洗动作
        results = []
        for action in actions:
            try:
                df = _apply_single_cleaning(df, action)
                results.append({"action": action, "status": "success", "message": "清洗动作应用成功"})
            except Exception as e:
                results.append({"action": action, "status": "error", "message": str(e)})

        return {"success": True, "results": results, "cleaned_rows": len(df), "cleaned_columns": len(df.columns)}

    except Exception as e:
        logger.exception("应用清洗动作失败")
        return {"success": False, "error": str(e), "results": []}


def apply_user_selected_cleaning(
    file_path: Path, selected_suggestions: list[dict[str, Any]], field_mappings: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    应用用户选择的清洗操作和字段映射

    Args:
        file_path: 文件路径
        selected_suggestions: 用户选择的清洗建议列表
        field_mappings: 字段映射字典 {原始字段名: 新字段名}

    Returns:
        包含清洗后数据和操作结果的字典
    """
    try:
        # 加载数据
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

        original_shape = df.shape
        logger.info(f"开始应用用户选择的清洗操作，原始数据: {original_shape[0]} 行 × {original_shape[1]} 列")

        # 记录应用的操作
        applied_operations = []

        # 1. 先应用字段映射（如果有）
        if field_mappings:
            # old_columns = df.columns.tolist()
            # 创建重命名映射，只处理实际存在的列
            rename_mapping = {
                old_name: new_name
                for old_name, new_name in field_mappings.items()
                if old_name in df.columns and old_name != new_name
            }

            if rename_mapping:
                df = df.rename(columns=rename_mapping)
                applied_operations.append(
                    {
                        "type": "column_rename",
                        "description": f"应用字段映射，重命名了 {len(rename_mapping)} 个列",
                        "details": rename_mapping,
                        "status": "success",
                    }
                )
                logger.info(f"应用字段映射: {rename_mapping}")

        # 2. 应用用户选择的清洗操作
        for suggestion in selected_suggestions:
            try:
                # 准备清洗参数
                cleaning_params = {
                    "column": suggestion.get("column"),
                    "issue_type": suggestion.get("issue_type") or suggestion.get("type"),
                    "parameters": suggestion.get("parameters", {}),
                    "suggested_action": suggestion.get("suggested_action"),
                    "method": suggestion.get("method"),
                }

                # 如果有字段映射，需要使用新的列名
                if field_mappings and cleaning_params["column"] in field_mappings:
                    old_column = cleaning_params["column"]
                    new_column = field_mappings[old_column]
                    cleaning_params["column"] = new_column
                    logger.info(f"清洗操作列名映射: {old_column} -> {new_column}")

                # 应用单个清洗操作
                before_shape = df.shape
                df = _apply_single_cleaning_enhanced(df, cleaning_params)
                after_shape = df.shape

                operation_result = {
                    "type": cleaning_params["issue_type"],
                    "column": cleaning_params["column"],
                    "description": suggestion.get("description", ""),
                    "suggested_action": cleaning_params["suggested_action"],
                    "before_shape": before_shape,
                    "after_shape": after_shape,
                    "status": "success",
                }
                applied_operations.append(operation_result)

                logger.info(f"应用清洗操作: {cleaning_params['issue_type']} on {cleaning_params['column']}")

            except Exception as e:
                logger.exception(f"应用清洗操作失败: {suggestion}")
                applied_operations.append(
                    {
                        "type": suggestion.get("issue_type", "unknown"),
                        "column": suggestion.get("column", "unknown"),
                        "description": suggestion.get("description", ""),
                        "error": str(e),
                        "status": "error",
                    }
                )

        final_shape = df.shape

        # 生成清洗总结
        successful_ops = [op for op in applied_operations if op["status"] == "success"]
        failed_ops = [op for op in applied_operations if op["status"] == "error"]

        summary = {
            "original_shape": original_shape,
            "final_shape": final_shape,
            "rows_changed": original_shape[0] - final_shape[0],
            "columns_changed": original_shape[1] - final_shape[1],
            "successful_operations": len(successful_ops),
            "failed_operations": len(failed_ops),
            "applied_field_mappings": bool(field_mappings),
            "field_mappings_count": len(field_mappings) if field_mappings else 0,
        }

        logger.info(f"清洗完成: {summary}")

        return {
            "success": True,
            "cleaned_data": df,
            "summary": summary,
            "applied_operations": applied_operations,
            "final_columns": df.columns.tolist(),
            "field_mappings_applied": field_mappings or {},
        }

    except Exception as e:
        logger.exception("应用用户选择的清洗操作失败")
        return {
            "success": False,
            "error": str(e),
            "cleaned_data": None,
            "summary": None,
            "applied_operations": [],
            "final_columns": [],
            "field_mappings_applied": {},
        }


def create_cleaning_suggestion(issue: dict[str, Any], df: pd.DataFrame) -> dict[str, Any] | None:
    """基于问题创建清洗建议"""
    issue_type = issue.get("type")
    column = issue.get("column")

    if issue_type == "missing_values":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue["description"],
            "suggested_action": "填充缺失值或删除含缺失值的行",
            "priority": issue["severity"],
            "parameters": {
                "method": "mean" if df[column].dtype in ["int64", "float64"] else "mode",
                "threshold": 0.5,
            },
            "auto_apply": False,
        }

    if issue_type == "duplicate_rows":
        return {
            "column": "all",
            "issue_type": issue_type,
            "description": issue["description"],
            "suggested_action": "删除重复行",
            "priority": "medium",
            "parameters": {"keep": "first"},
            "auto_apply": True,
        }

    if issue_type == "column_name":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue["description"],
            "suggested_action": "规范化列名",
            "priority": "low",
            "parameters": {"method": "normalize"},
            "auto_apply": True,
        }

    if issue_type == "data_type":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue["description"],
            "suggested_action": f"转换为{issue['suggested_type']}类型",
            "priority": "medium",
            "parameters": {"target_type": issue["suggested_type"]},
            "auto_apply": False,
        }

    return None


PROMPT_CLEANING_SUGGESTION = """
基于用户的清洗要求，为以下数据集生成具体的清洗建议。

数据概览:
{data_overview}

用户要求:
{user_requirements}

请生成清洗建议，以JSON格式返回:
{{
  "suggestions": [
    {{
      "column": "列名",
      "issue_type": "问题类型",
      "description": "问题描述",
      "suggested_action": "建议的清洗动作",
      "priority": "优先级(high/medium/low)",
      "parameters": {{"参数名": "参数值"}},
      "auto_apply": false
    }}
  ]
}}

要求:
1. 建议要具体、可执行
2. 优先级要合理
3. 参数要完整
4. 只有安全的操作才设置auto_apply为true
"""


def _chain_prompt(input: tuple[pd.DataFrame, str]) -> str:
    df, user_requirements = input
    return PROMPT_CLEANING_SUGGESTION.format(
        data_overview=df.describe().to_json(),
        user_requirements=user_requirements or "无特殊要求",
    )


def _chain_parse(response: str) -> list[dict[str, Any]]:
    try:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            return parsed.get("suggestions", [])
        logger.warning("无法从LLM响应中提取JSON格式的清洗建议")
        return []
    except Exception as e:
        logger.error(f"解析清洗建议失败: {e}")
        return []


def generate_suggestions(state: CleaningState) -> CleaningState:
    """生成清洗建议"""
    try:
        df_data = state["df_data"]
        issues = state["quality_issues"]
        user_requirements = state.get("user_requirements", "")

        if df_data is None:
            raise ValueError("数据未加载")

        df = pd.DataFrame(df_data)  # 反序列化DataFrame

        logger.info("开始生成清洗建议")

        # 基于质量问题生成建议
        suggestions = [suggestion for issue in issues if (suggestion := create_cleaning_suggestion(issue, df))]

        # 如果有用户自定义要求，使用LLM生成额外建议
        if user_requirements:
            chain = _chain_prompt | get_llm() | _chain_parse
            suggestions.extend(chain.invoke((df, user_requirements)))

        state["cleaning_suggestions"] = suggestions
        logger.info(f"生成了 {len(suggestions)} 个清洗建议")
        return state

    except Exception as e:
        logger.error(f"生成清洗建议失败: {e}")
        state["error_message"] = str(e)
        return state


def generate_cleaning_summary(state: CleaningState) -> CleaningState:
    """生成清洗总结"""
    try:
        df_data = state["df_data"]
        cleaned_df_data = state["cleaned_df_data"]
        suggestions = state["cleaning_suggestions"]
        field_mappings = state["field_mappings"]

        logger.info("开始生成清洗总结")

        # 构建总结信息
        summary_parts = []

        # 基本信息对比
        if df_data is not None and cleaned_df_data is not None:
            df = pd.DataFrame(df_data)  # 反序列化DataFrame
            cleaned_df = pd.DataFrame(cleaned_df_data)  # 反序列化DataFrame
            summary_parts.append(f"原始数据: {len(df)} 行, {len(df.columns)} 列")
            summary_parts.append(f"清洗后数据: {len(cleaned_df)} 行, {len(cleaned_df.columns)} 列")

        # 字段映射信息
        if field_mappings:
            summary_parts.append(f"字段映射: 识别了 {len(field_mappings)} 个字段的含义")

        # 清洗建议信息
        if suggestions:
            summary_parts.append(f"清洗建议: 生成了 {len(suggestions)} 个建议")

        summary = "\n".join(summary_parts)
        state["cleaning_summary"] = summary

        logger.info("清洗总结生成完成")
        return state

    except Exception as e:
        logger.error(f"生成清洗总结失败: {e}")
        state["error_message"] = str(e)
        return state
