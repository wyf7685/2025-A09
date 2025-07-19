"""
基于LangChain和LangGraph的智能数据清洗Agent
支持用户自定义清洗要求，LLM猜测数据源字段名并保存
"""

import threading
from pathlib import Path
from typing import Any, cast

import pandas as pd
from langchain_core.runnables import ensure_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.log import logger

from ._clean import (
    apply_cleaning,
    apply_cleaning_actions,
    apply_user_selected_cleaning,
    generate_cleaning_summary,
    generate_suggestions,
)
from ._fields import guess_field_names
from ._load_data import load_data
from ._quality import analyze_quality, calculate_quality_score
from .schemas import CleaningState, DataQualityReport


def _create_graph() -> CompiledStateGraph[CleaningState, CleaningState, CleaningState]:
    """创建数据清洗工作流图"""
    graph = StateGraph(CleaningState)

    # 添加节点
    graph.add_node("load_data", load_data)
    graph.add_node("analyze_quality", analyze_quality)
    graph.add_node("guess_field_names", guess_field_names)
    graph.add_node("generate_suggestions", generate_suggestions)
    graph.add_node("apply_cleaning", apply_cleaning)
    graph.add_node("generate_summary", generate_cleaning_summary)

    # 设置起始节点
    graph.set_entry_point("load_data")

    # 添加边
    graph.add_edge("load_data", "analyze_quality")
    graph.add_edge("analyze_quality", "guess_field_names")
    graph.add_edge("guess_field_names", "generate_suggestions")
    graph.add_edge("generate_suggestions", "apply_cleaning")
    graph.add_edge("apply_cleaning", "generate_summary")
    graph.add_edge("generate_summary", END)

    return graph.compile(checkpointer=InMemorySaver())


class SmartCleanDataAgent:
    """基于LangChain和LangGraph的智能数据清洗Agent"""

    def __init__(self) -> None:
        self._graph = _create_graph()
        # Export methods
        self.apply_cleaning_actions = apply_cleaning_actions
        self.apply_user_selected_cleaning = apply_user_selected_cleaning

    def process_and_clean_file(
        self,
        file_path: Path,
        user_requirements: str | None = None,
        selected_suggestions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        分析并清洗数据文件的完整流程

        Args:
            file_path: 文件路径
            user_requirements: 用户自定义清洗要求
            selected_suggestions: 用户选择的清洗建议（如果为None则自动应用所有建议）

        Returns:
            包含分析结果和清洗后数据的完整结果
        """
        try:
            # 1. 先进行标准的数据质量分析
            analysis_result = self.process_file(file_path, user_requirements)

            if not analysis_result["success"]:
                return analysis_result

            # 2. 如果没有指定选择的建议，使用所有自动应用的建议
            if selected_suggestions is None:
                selected_suggestions = [
                    suggestion
                    for suggestion in analysis_result.get("cleaning_suggestions", [])
                    if suggestion.get("auto_apply", False)
                ]

            # 3. 应用用户选择的清洗操作
            cleaning_result = apply_user_selected_cleaning(
                file_path=file_path,
                selected_suggestions=selected_suggestions,
                field_mappings=analysis_result.get("field_mappings", {}),
            )

            if not cleaning_result["success"]:
                return {
                    "success": False,
                    "error": cleaning_result["error"],
                    "analysis_result": analysis_result,
                    "cleaning_result": None,
                }

            # 4. 合并结果
            return {
                "success": True,
                "analysis_result": analysis_result,
                "cleaning_result": cleaning_result,
                "final_data": cleaning_result["cleaned_data"],
                "field_mappings": analysis_result.get("field_mappings", {}),
                "applied_operations": cleaning_result["applied_operations"],
                "summary": {"analysis": analysis_result.get("summary", ""), "cleaning": cleaning_result["summary"]},
            }

        except Exception as e:
            logger.error(f"处理和清洗文件失败: {e}")
            return {"success": False, "error": str(e), "analysis_result": None, "cleaning_result": None}

    def process_file(self, file_path: Path, user_requirements: str | None = None) -> dict[str, Any]:
        """处理数据文件的主要入口"""
        try:
            # 初始化状态
            initial_state = CleaningState(
                file_path=file_path,
                df_data=None,
                user_requirements=user_requirements,
                quality_issues=[],
                field_mappings={},
                cleaning_suggestions=[],
                cleaned_df_data=None,
                cleaning_summary="",
                error_message=None,
            )

            # 执行工作流
            config = ensure_config({"configurable": {"thread_id": threading.get_ident()}})
            result = cast("CleaningState", self._graph.invoke(initial_state, config))

            # 构建返回结果
            if error_message := result.get("error_message"):
                return {
                    "success": False,
                    "error": error_message,
                    "quality_report": None,
                    "field_mappings": {},
                    "cleaning_suggestions": [],
                    "summary": "",
                }

            # 构建质量报告
            df_data = result.get("df_data")
            quality_report = None
            if df_data is not None:
                df = pd.DataFrame(df_data)  # 反序列化DataFrame
                quality_report = DataQualityReport(
                    overall_score=calculate_quality_score(result["quality_issues"]),
                    total_rows=len(df),
                    total_columns=len(df.columns),
                    missing_values_count=int(df.isna().sum().sum()),
                    duplicate_rows_count=int(df.duplicated().sum()),
                    issues=result["quality_issues"],
                    recommendations=[s.get("suggested_action", "") for s in result["cleaning_suggestions"]],
                ).model_dump()

            return {
                "success": True,
                "quality_report": quality_report,
                "field_mappings": result["field_mappings"],
                "cleaning_suggestions": result["cleaning_suggestions"],
                "summary": result["cleaning_summary"],
            }

        except Exception as e:
            logger.error(f"处理文件失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "quality_report": None,
                "field_mappings": {},
                "cleaning_suggestions": [],
                "summary": "",
            }


# 创建全局实例
smart_clean_agent = SmartCleanDataAgent()
