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
                        df = df.rename(columns={original: new_name})
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

        # 记录映射后的列名
        columns_after_mapping = df.columns.tolist()
        logger.info(f"字段映射后的列名: {columns_after_mapping}")

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
        
        # 验证字段映射是否被保留
        logger.info(f"执行清洗后的列名: {final_columns}")
        if field_mappings_applied and final_columns != columns_after_mapping:
            logger.warning(f"警告：列名在清洗过程中被改变！")
            logger.warning(f"预期的列名: {columns_after_mapping}")
            logger.warning(f"实际的列名: {final_columns}")
            logger.warning(f"生成的代码可能意外修改了字段映射")

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
    # 统一兼容质量问题的类型字段，支持 'type' 和 'issue_type'
    issue_type = issue.get("type") or issue.get("issue_type")
    column = issue.get("column", "all")

    if issue_type == "missing_values":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue.get("description", "该列存在缺失值"),
            "suggested_action": "填充缺失值",
            "priority": "high",
            "parameters": {"strategy": "median"},
            "auto_apply": True,
        }

    if issue_type == "duplicate_rows":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue.get("description", "存在重复行"),
            "suggested_action": "删除重复行",
            "priority": "medium",
            "parameters": {"keep": "first"},
            "auto_apply": True,
        }

    if issue_type == "data_type":
        suggested_type = issue.get("suggested_type") or issue.get("target_type") or "string"
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue.get("description", f"建议转换为{suggested_type}类型"),
            "suggested_action": f"转换为{suggested_type}类型",
            "priority": "medium",
            "parameters": {"target_type": suggested_type},
            "auto_apply": False,
        }

    if issue_type == "column_name":
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue.get("description", "列名存在格式问题"),
            "suggested_action": "标准化列名",
            "priority": "low",
            "parameters": {"replace_spaces": True, "normalize_case": "snake_case"},
            "auto_apply": False,
        }

    if issue_type == "outliers":
        bounds = issue.get("bounds", {})
        return {
            "column": column,
            "issue_type": issue_type,
            "description": issue.get("description", "存在异常值"),
            "suggested_action": "处理异常值",
            "priority": "medium",
            "parameters": {"method": "clip", "lower": bounds.get("lower"), "upper": bounds.get("upper")},
            "auto_apply": False,
        }

    return None


class LLMCleaningSuggestionResponse(BaseModel):
    suggestions: list[dict[str, Any]]


# 新增：建议去重规范化与质量问题摘要辅助函数
def _normalize_column_name(name: str | None) -> str:
    n = (str(name) if name is not None else "all").strip().lower()
    # 去除包裹的引号与反引号
    n = n.strip("'\"`")
    # 空白转下划线
    n = re.sub(r"\s+", "_", n)
    # 非字母数字统一为下划线
    n = re.sub(r"[^a-z0-9_]+", "_", n)
    # 压缩多余下划线并去除首尾
    n = re.sub(r"_+", "_", n).strip("_")
    return n if n else "all"


def _normalize_action(action: str | None) -> str:
    if not action:
        return ""
    a = action.strip().lower()
    # 同义归一
    if ("重复" in a) or ("去重" in a) or ("重复行" in a) or ("重复记录" in a):
        return "删除重复行"
    if ("缺失" in a) or ("空值" in a) or ("null" in a):
        return "填充缺失值"
    if ("标准化" in a and "列名" in a) or ("列名" in a and ("规范" in a or "格式" in a)):
        return "标准化列名"
    if ("异常" in a) or ("离群" in a) or ("outlier" in a):
        return "处理异常值"
    if ("转换" in a and "类型" in a) or ("类型转换" in a):
        return "转换类型"
    return action


def _infer_type_from_action(action: str | None) -> str | None:
    a = _normalize_action(action)
    if a == "删除重复行":
        return "duplicate_rows"
    if a == "填充缺失值":
        return "missing_values"
    if a == "标准化列名":
        return "column_name"
    if a == "处理异常值":
        return "outliers"
    if a == "转换类型":
        return "data_type"
    return None


def _param_signature(params: dict[str, Any] | None) -> str:
    if not params:
        return "-"
    try:
        items = sorted((str(k), str(v)) for k, v in params.items())
        return ";".join(f"{k}={v}" for k, v in items)
    except Exception:
        return "-"


def _summarize_quality_issues(issues: list[dict[str, Any]], max_per_type: int = 5) -> str:
    groups: dict[str, list[dict[str, Any]]] = {
        "missing_values": [],
        "duplicate_rows": [],
        "data_type": [],
        "column_name": [],
        "outliers": [],
    }
    for it in issues:
        t = it.get("type") or it.get("issue_type")
        if t in groups:
            groups[t].append(it)

    parts: list[str] = []

    if groups["missing_values"]:
        items = sorted(groups["missing_values"], key=lambda x: x.get("count", 0), reverse=True)[:max_per_type]
        sample = ", ".join(
            (
                f"{i.get('column', '?')}("
                f"{i.get('count', 0)}"
                f"{';' + format(i.get('rate', 0) * 100, '.1f') + '%' if i.get('rate') is not None else ''}"
                ")"
            ).rstrip(";")
            for i in items
        )
        parts.append(f"缺失值: {len(groups['missing_values'])}列；示例: {sample}")

    if groups["duplicate_rows"]:
        c = groups["duplicate_rows"][0].get("count", len(groups["duplicate_rows"]))
        parts.append(f"重复行: {c}行")

    if groups["data_type"]:
        items = groups["data_type"][:max_per_type]
        sample = ", ".join(f"{i.get('column', '?')}→{i.get('suggested_type', '')}" for i in items)
        parts.append(f"类型建议: {len(groups['data_type'])}列；示例: {sample}")

    if groups["column_name"]:
        items = groups["column_name"][:max_per_type]
        sample = ", ".join(f"{i.get('column', '?')}" for i in items)
        parts.append(f"列名问题: {len(groups['column_name'])}列；示例: {sample}")

    if groups["outliers"]:
        items = sorted(groups["outliers"], key=lambda x: x.get("count", 0), reverse=True)[:max_per_type]
        sample = ", ".join(f"{i.get('column', '?')}({i.get('count', 0)})" for i in items)
        parts.append(f"异常值: {len(groups['outliers'])}列；示例: {sample}")

    summary = "；".join(parts)
    return summary[:1000] if summary else "无显著质量问题"


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

    logger.info("开始生成清洗建议...")
    # 不再使用规则化映射，完全由LLM生成
    issues = state["quality_issues"]

    # 使用LLM生成建议
    try:
        model_id = state.get("model_id")
        user_requirements = state.get("user_requirements") or "无特殊要求"
        data_overview = source.format_overview()
        issues_summary = _summarize_quality_issues(issues)
        prompt = PROMPTS.clean_suggestion.format(
            data_overview=data_overview,
            user_requirements=user_requirements,
            issues_summary=issues_summary,
        )
        llm = get_llm(model_id)
        response = llm.invoke(prompt)
        llm_suggestions = _chain_parse(response)
    except Exception as e:
        logger.error(f"LLM生成清洗建议失败: {e}")
        llm_suggestions = []

    # 统一字段与默认值，并增强规范化（补齐参数中的计数）
    normalized: list[dict[str, Any]] = []
    for s in llm_suggestions:
        s = s.copy()
        # 确保有type字段
        s_type = s.get("type") or s.get("issue_type")
        if not s_type:
            inferred = _infer_type_from_action(s.get("suggested_action"))
            if inferred:
                s_type = inferred
        if s_type:
            s["type"] = s_type  # 与前端保持一致
        # 默认优先级
        if not s.get("priority"):
            s["priority"] = "medium"
        # 补齐参数
        if not s.get("parameters"):
            s["parameters"] = {}
        # 从描述或标题中提取计数，便于统一去重
        cnt = _extract_count_from_text(s.get("description") or s.get("title"))
        if cnt is not None and "count" not in s["parameters"]:
            s["parameters"]["count"] = cnt
        normalized.append(s)

    # 分组合并：按规范化动作+模糊列名分组，取信息量更高的一项并合并参数
    groups: list[dict[str, Any]] = []
    for s in normalized:
        norm_action = _normalize_action(s.get("suggested_action", ""))
        col = s.get("column", "all")
        placed = False
        for g in groups:
            if g["norm_action"] == norm_action and _similar_column(col, g["column"]):
                g["items"].append(s)
                placed = True
                break
        if not placed:
            groups.append({"norm_action": norm_action, "column": col, "items": [s]})

    deduped: list[dict[str, Any]] = []
    for g in groups:
        # 选择代表项：优先有参数，再看优先级
        rep = max(g["items"], key=lambda x: (bool(x.get("parameters")), _priority_rank(x.get("priority"))))
        # 合并参数（不覆盖代表项已有参数）
        merged_params = _merge_params(g["items"])
        rep_params = rep.get("parameters") or {}
        for k, v in merged_params.items():
            if k not in rep_params:
                rep_params[k] = v
        rep["parameters"] = rep_params
        # 规范化列名写回统一值（使用最规范化后的格式）
        rep["column"] = _normalize_column_name(rep.get("column"))
        # 规范化动作写回统一值
        rep["suggested_action"] = g["norm_action"] or rep.get("suggested_action", "")
        deduped.append(rep)

    # 额外合并：同为数据类型转换的多列合并为一条（columns列表）
    dtype_groups: list[dict[str, Any]] = []
    for s in deduped:
        if s.get("type") == "data_type" and _normalize_action(s.get("suggested_action", "")) == "转换类型":
            dtype_groups.append(s)  # noqa: PERF401
    if len(dtype_groups) > 1:
        # 从deduped移除这些项
        deduped = [s for s in deduped if s not in dtype_groups]
        # 构造合并项
        base = dtype_groups[0].copy()
        # 收集所有列（使用当前写回的列名，已规范化）
        columns = [s.get("column", "") for s in dtype_groups if s.get("column")]
        base["column"] = "multiple"
        base["columns"] = columns
        # 描述可略微泛化为多列处理提示
        if base.get("description"):
            base["description"] = f"多列数据类型检查与转换（共{len(columns)}列）"
        deduped.append(base)

    logger.info(f"生成清洗建议完成，LLM {len(llm_suggestions)} 条，去重后 {len(deduped)} 条")

    state["cleaning_suggestions"] = deduped
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


# 新增：模糊列名匹配与参数增强
def _similar_column(a: str | None, b: str | None) -> bool:
    na = _normalize_column_name(a)
    nb = _normalize_column_name(b)
    if na == nb:
        return True
    import difflib

    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.95


def _priority_rank(p: str | None) -> int:
    if not p:
        return 0
    m = {"low": 1, "medium": 2, "high": 3}
    return m.get(p.lower(), 1)


def _merge_params(items: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for it in items:
        params = it.get("parameters") or {}
        for k, v in params.items():
            if k not in merged:
                merged[k] = v
    return merged


def _extract_count_from_text(text: str | None) -> int | None:
    if not text:
        return None
    # 优先匹配括号中的数字，例如：(154)
    m = re.search(r"[（\(]\s*(\d+)\s*[）\)]", text)
    if m:
        try:
            return int(m.group(1))
        except Exception as e:
            logger.debug(f"解析计数失败: {e}")
    # 退化为任意数字
    m2 = re.findall(r"\d+", text)
    if m2:
        try:
            return int(m2[-1])
        except Exception:
            return None
    return None
