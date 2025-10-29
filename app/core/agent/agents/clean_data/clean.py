import re
from pathlib import Path
from typing import Any

import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from app.core.agent.prompts.clean_data import PROMPTS
from app.core.agent.schemas import OperationFailedModel
from app.core.chain import get_llm
from app.core.chain.nl_analysis import code_parser
from app.core.datasource import create_df_source
from app.core.executor import CodeExecutor
from app.log import logger
from app.services.datasource import temp_source_service

from .schemas import ApplyCleaningResult, ApplyCleaningSummary, CleaningState, load_source


def _create_code_generator_chain(model_id: str | None = None) -> Runnable[dict[str, Any], str]:
    prompt = PromptTemplate(
        input_variables=["data_overview", "selected_suggestions", "user_requirements"],
        template=PROMPTS.generate_clean_code,
    )
    return prompt | get_llm(model_id) | code_parser


def apply_user_selected_cleaning_with_ai(
    file_path: Path,
    selected_suggestions: list[dict[str, Any]],
    field_mappings: dict[str, str] | None = None,
    user_requirements: str | None = None,
    model_id: str | None = None,
) -> ApplyCleaningResult | OperationFailedModel:
    """
    使用AI生成代码来执行用户选择的清洗操作和字段映射

    Args:
        file_path: 文件路径
        selected_suggestions: 用户选择的清洗建议列表
        field_mappings: 字段映射字典 {原始字段名: 新字段名}
        user_requirements: 用户自定义要求
        model_id: 选择用于生成清洗代码的LLM模型ID或名称

    Returns:
        包含清洗后数据和操作结果的字典
    """
    try:
        logger.info("=== AI驱动的数据清洗开始 ===")
        logger.info(f"文件路径: {file_path}")
        logger.info(f"清洗建议数量: {len(selected_suggestions)}")
        logger.info(f"字段映射: {field_mappings}")
        logger.info(f"用户要求: {user_requirements}")

        # 加载数据
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

        original_shape = df.shape
        original_columns = df.columns.tolist()
        logger.info(f"原始数据: {original_shape[0]} 行 × {original_shape[1]} 列")

        # 第一步：如果有字段映射，先应用字段映射
        field_mappings_applied: dict[str, str] = {}
        if field_mappings:
            logger.info("开始应用字段映射...")
            try:
                for original, new_name in field_mappings.items():
                    if original in df.columns:
                        df.rename(columns={original: new_name}, inplace=True)
                        field_mappings_applied[original] = new_name
                        logger.debug(f"字段映射: {original} -> {new_name}")
                    else:
                        logger.warning(f"字段映射跳过，未找到列: {original}")
            except Exception as e:
                logger.error(f"应用字段映射失败: {e}")
                return OperationFailedModel(message=f"应用字段映射失败: {e}", error_type="FieldMappingError")

            # 如果只进行字段映射，不执行进一步的清洗
            if not selected_suggestions:
                logger.info("未提供清洗建议，仅应用了字段映射")
                final_shape = df.shape
                final_columns = df.columns.tolist()

                applied_operations = []
                summary = ApplyCleaningSummary(
                    original_shape=original_shape,
                    final_shape=final_shape,
                    rows_changed=0,
                    columns_changed=0,
                    successful_operations=len(applied_operations),
                    failed_operations=0,
                    applied_field_mappings=bool(field_mappings_applied),
                    field_mappings_count=len(field_mappings_applied),
                )

                return ApplyCleaningResult(
                    cleaned_data=df,
                    summary=summary,
                    applied_operations=applied_operations,
                    final_columns=df.columns.tolist(),
                    field_mappings_applied=field_mappings_applied,
                    generated_code="# 只应用字段映射，无需生成清洗代码",
                )

        # 第二步：在映射后的数据上执行清洗操作
        logger.info("开始在映射后的数据上执行清洗操作...")

        # 更新清洗建议中的列名为映射后的列名
        updated_suggestions = []
        for suggestion in selected_suggestions:
            updated_suggestion = suggestion.copy()
            if suggestion.get("column") and suggestion["column"] != "all":
                old_column = suggestion["column"]
                # 查找映射后的列名
                new_column = field_mappings_applied.get(old_column, old_column)
                updated_suggestion["column"] = new_column
                logger.debug(f"更新清洗建议中的列名: {old_column} -> {new_column}")
            updated_suggestions.append(updated_suggestion)

        # 创建数据源并执行代码
        data_source = create_df_source(df, "temp_data", "临时数据用于清洗")

        # 准备数据信息给AI
        data_info = {
            "data_overview": data_source.format_overview(),
            "selected_suggestions": updated_suggestions,  # 使用更新后的建议
            "user_requirements": user_requirements or "无特殊要求",
        }

        # 生成清洗代码（使用指定模型）
        logger.info("开始生成清洗代码...")
        generated_code = _create_code_generator_chain(model_id).invoke(data_info)
        logger.info(f"生成的清洗代码:\n{generated_code}")

        with CodeExecutor(data_source) as executor:
            exec_result = executor.execute(generated_code + "\n\nresult = df")
        del df, data_source

        if not exec_result["success"]:
            raise ValueError(f"代码执行失败: {exec_result['error']}")

        # 获取执行结果
        if exec_result["result"] is None:
            raise ValueError("代码执行没有返回结果")

        cleaned_df = exec_result["result"]

        if not isinstance(cleaned_df, pd.DataFrame):
            raise TypeError(f"代码执行结果不是DataFrame: {type(cleaned_df)}")

        final_shape = cleaned_df.shape
        final_columns = cleaned_df.columns.tolist()

        # 构建操作记录
        applied_operations = []

        if field_mappings_applied:
            applied_operations.append(
                {
                    "type": "field_mapping",
                    "details": field_mappings_applied,
                }
            )

        # 构建清洗总结
        summary = ApplyCleaningSummary(
            original_shape=original_shape,
            final_shape=final_shape,
            rows_changed=final_shape[0] - original_shape[0],
            columns_changed=len(final_columns) - len(original_columns),
            successful_operations=len(applied_operations),
            failed_operations=0,
            applied_field_mappings=bool(field_mappings_applied),
            field_mappings_count=len(field_mappings_applied),
        )

        return ApplyCleaningResult(
            cleaned_data=cleaned_df,
            summary=summary,
            applied_operations=applied_operations,
            final_columns=final_columns,
            field_mappings_applied=field_mappings_applied,
            generated_code=generated_code,
        )

    except Exception as err:
        logger.exception("AI驱动的数据清洗失败")
        return OperationFailedModel.from_err(err)


def _format_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    # 这里是建议格式转换的示例，可按需调整
    issue_type = issue.get("issue_type")
    column = issue.get("column", "all")

    if issue_type == "missing_values":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue["description"],
            "suggested_action": "填充缺失值",
            "priority": "high",
            "parameters": {"strategy": "median"},
            "auto_apply": True,
        }

    if issue_type == "duplicates":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue["description"],
            "suggested_action": "删除重复行",
            "priority": "medium",
            "parameters": {"keep": "first"},
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


class LLMCleaningSuggestionResponse(BaseModel):
    suggestions: list[dict[str, Any]]


def _chain_parse(response: str) -> list[dict[str, Any]]:
    try:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            return LLMCleaningSuggestionResponse.model_validate_json(json_match.group(0)).suggestions
        logger.warning("无法从LLM响应中提取JSON格式的清洗建议")
        return []
    except Exception as e:
        logger.error(f"解析清洗建议失败: {e}")
        return []


def generate_suggestions(state: CleaningState) -> CleaningState:
    source = load_source(state, "source_id")
    df = source.get_full()

    logger.info("开始生成清洗建议...")
    # 分析数据质量问题并生成建议
    issues = state["quality_issues"]
    suggestions = []

    for issue in issues:
        formatted = _format_issue(issue)
        if formatted:
            suggestions.append(formatted)

    # 记录建议数量
    logger.info(f"生成清洗建议完成，共 {len(suggestions)} 条")

    state["cleaning_suggestions"] = suggestions
    return state


def generate_cleaning_summary(state: CleaningState) -> CleaningState:
    source = load_source(state, "cleaned_source_id")
    df = source.get_full()

    logger.info("开始生成清洗总结...")

    # 生成清洗总结（分析阶段仅生成文本概要，非结构化模型）
    initial_rows = len(df)
    final_rows = len(df)
    initial_cols = len(df.columns)
    final_cols = len(df.columns)
    field_mappings = state.get("field_mappings", {})
    field_mappings_count = len(field_mappings)

    summary_text = (
        f"原始形状: {initial_rows} 行 × {initial_cols} 列；"
        f"当前形状: {final_rows} 行 × {final_cols} 列；"
        f"行变更: {final_rows - initial_rows}；"
        f"列变更: {final_cols - initial_cols}；"
        f"字段映射数量: {field_mappings_count}"
    )

    logger.info("清洗总结生成完成")

    state["cleaning_summary"] = summary_text
    return state


def apply_cleaning(state: CleaningState) -> CleaningState:
    """应用清洗操作的节点函数 - 在分析阶段不执行实际清洗，只准备数据"""
    source = load_source(state, "source_id")

    logger.info("准备清洗数据（分析阶段不执行实际清洗）")

    # 在分析阶段，我们不执行实际的清洗操作
    # 只是将原数据复制到cleaned_df_data，为后续的总结生成做准备
    state["cleaned_source_id"] = temp_source_service.register(source.copy_with_data())

    logger.info("清洗数据准备完成")
    return state


def apply_cleaning_actions(
    file_path: Path,
    selected_suggestions: list[dict[str, Any]],
    field_mappings: dict[str, str] | None = None,
    user_requirements: str | None = None,
    model_id: str | None = None,
) -> ApplyCleaningResult | OperationFailedModel:
    """
    应用清洗操作的公共接口函数

    这是对apply_user_selected_cleaning_with_ai的包装，提供更简洁的接口
    """
    return apply_user_selected_cleaning_with_ai(
        file_path=file_path,
        selected_suggestions=selected_suggestions,
        field_mappings=field_mappings,
        user_requirements=user_requirements,
        model_id=model_id,
    )
