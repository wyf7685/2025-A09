import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_core.runnables import Runnable

from app.core.agent.schemas import OperationFailedModel
from app.core.chain import get_llm
from app.core.chain.nl_analysis import code_parser
from app.core.datasource import create_df_source
from app.core.executor import CodeExecutor
from app.log import logger
from app.services.datasource import temp_source_service

from .schemas import ApplyCleaningResult, ApplyCleaningSummary, CleaningState, load_source

# AI代码生成的提示模板
CODE_GENERATION_PROMPT = """
你是一位专业的数据清洗专家。基于用户的要求，为以下数据生成Python代码来执行数据清洗操作。

数据信息:
{data_overview}

用户选择的清洗操作:
{selected_suggestions}

用户自定义要求:
{user_requirements}

请生成Python代码来执行以下操作:
1. 执行用户选择的清洗操作
2. 确保最终的DataFrame列名是映射后的名称

要求:
- 使用变量名 `df` 来表示DataFrame
- 最终返回清洗后的DataFrame: `result = df`
- 代码要安全、高效
- 包含适当的错误处理
- 添加注释说明每个步骤

生成的代码:
```python
import pandas as pd
import numpy as np

# 你的清洗代码
```
"""


def _create_code_generator_chain() -> Runnable[dict[str, Any], str]:
    prompt = PromptTemplate(
        input_variables=["data_overview", "selected_suggestions", "user_requirements"],
        template=CODE_GENERATION_PROMPT,
    )
    return prompt | get_llm() | code_parser


def apply_user_selected_cleaning_with_ai(
    file_path: Path,
    selected_suggestions: list[dict[str, Any]],
    field_mappings: dict[str, str] | None = None,
    user_requirements: str | None = None,
) -> ApplyCleaningResult | OperationFailedModel:
    """
    使用AI生成代码来执行用户选择的清洗操作和字段映射

    Args:
        file_path: 文件路径
        selected_suggestions: 用户选择的清洗建议列表
        field_mappings: 字段映射字典 {原始字段名: 新字段名}
        user_requirements: 用户自定义要求

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
        logger.info(f"原始列名: {original_columns}")

        # 第一步：先应用字段映射（如果有的话）
        field_mappings_applied = {}
        if field_mappings:
            logger.info("开始应用字段映射...")
            for old_name, new_name in field_mappings.items():
                if old_name in df.columns:
                    df = df.rename(columns={old_name: new_name})
                    field_mappings_applied[old_name] = new_name
                    logger.info(f"字段映射: {old_name} -> {new_name}")

            logger.info(f"字段映射完成，应用了 {len(field_mappings_applied)} 个映射")
            logger.info(f"映射后列名: {df.columns.tolist()}")

        # 如果没有清洗操作，只返回应用字段映射后的数据
        if not selected_suggestions:
            logger.info("没有清洗操作，只应用字段映射")

            applied_operations = []
            if field_mappings_applied:
                applied_operations[:] = [
                    {
                        "type": "field_mapping",
                        "description": f"应用字段映射，重命名了 {len(field_mappings_applied)} 个列",
                        "status": "success",
                        "details": field_mappings_applied,
                    }
                ]

            summary = ApplyCleaningSummary(
                original_shape=original_shape,
                final_shape=df.shape,
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

        # 生成清洗代码
        logger.info("开始生成清洗代码...")
        generated_code = _create_code_generator_chain().invoke(data_info)
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
                    "description": f"应用字段映射，重命名了 {len(field_mappings_applied)} 个列",
                    "status": "success",
                    "details": field_mappings_applied,
                }
            )

        if selected_suggestions:
            applied_operations.append(
                {
                    "type": "ai_generated_cleaning",
                    "description": f"AI生成代码执行清洗操作，包含 {len(selected_suggestions)} 个清洗建议",
                    "status": "success",
                    "details": {
                        "field_mappings_count": len(field_mappings_applied),
                        "suggestions_count": len(selected_suggestions),
                    },
                }
            )

        summary = ApplyCleaningSummary(
            original_shape=original_shape,
            final_shape=final_shape,
            rows_changed=original_shape[0] - final_shape[0],
            columns_changed=original_shape[1] - final_shape[1],
            successful_operations=len(applied_operations),
            failed_operations=0,
            applied_field_mappings=bool(field_mappings_applied),
            field_mappings_count=len(field_mappings_applied),
        )

        logger.info("=== AI驱动的清洗完成 ===")
        logger.info(f"最终数据形状: {final_shape}")
        logger.info(f"最终列名: {final_columns}")
        logger.info(f"应用的字段映射: {field_mappings_applied}")

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
            "auto_apply": False,  # 改为False，不自动应用
        }

    if issue_type == "column_name":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue["description"],
            "suggested_action": "规范化列名",
            "priority": "low",
            "parameters": {"method": "normalize"},
            "auto_apply": False,  # 改为False，不自动应用
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
        if (source_id := state.get("source_id")) is None or (source := temp_source_service.get(source_id)) is None:
            raise ValueError("数据未加载")

        issues = state["quality_issues"]
        user_requirements = state.get("user_requirements", "")

        df = source.get_full()  # 反序列化DataFrame

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
        suggestions = state["cleaning_suggestions"]
        field_mappings = state["field_mappings"]

        logger.info("开始生成清洗总结")

        # 构建总结信息
        summary_parts = []

        # 基本信息对比
        df = load_source(state, "source_id").get_full()
        cleaned_df = load_source(state, "cleaned_source_id").get_full()
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
    )
