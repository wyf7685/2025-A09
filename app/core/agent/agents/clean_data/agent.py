"""
基于LangChain和LangGraph的智能数据清洗Agent
支持用户自定义清洗要求，LLM猜测数据源字段名并保存
"""

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import anyio.to_thread
from langchain_core.runnables import ensure_config

from app.core.agent.schemas import OperationFailedModel, is_failed, is_success
from app.log import logger
from app.services.datasource import temp_source_service
from app.utils import copy_param_annotations

from .clean import (
    apply_cleaning,
    apply_cleaning_actions,
    apply_user_selected_cleaning_with_ai,
    generate_cleaning_summary,
    generate_suggestions,
)
from .fields import guess_field_names
from .load_data import load_data
from .quality import analyze_quality, calculate_quality_score
from .schemas import (
    ApplyCleaningResult,
    CleaningState,
    DataQualityReport,
    ProcessCleanFileResult,
    ProcessCleanFileSummary,
    ProcessFileResult,
    load_source,
)

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

type AgentGraph = CompiledStateGraph[CleaningState, None, CleaningState, CleaningState]


def _create_graph() -> AgentGraph:
    """创建数据清洗工作流图"""
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, StateGraph

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
    _graph: AgentGraph = _create_graph()

    @staticmethod
    @copy_param_annotations(apply_cleaning_actions)
    async def apply_cleaning_actions(*args: Any, **kwargs: Any) -> ApplyCleaningResult | OperationFailedModel:
        def wrapper() -> ApplyCleaningResult | OperationFailedModel:
            return apply_cleaning_actions(*args, **kwargs)

        return await anyio.to_thread.run_sync(wrapper, abandon_on_cancel=True)

    @staticmethod
    @copy_param_annotations(apply_user_selected_cleaning_with_ai)
    async def apply_user_selected_cleaning(
        *args: Any,
        **kwargs: Any,
    ) -> ApplyCleaningResult | OperationFailedModel:
        def wrapper() -> ApplyCleaningResult | OperationFailedModel:
            return apply_user_selected_cleaning_with_ai(*args, **kwargs)

        return await anyio.to_thread.run_sync(wrapper, abandon_on_cancel=True)

    async def process_and_clean_file(
        self,
        model_id: str,
        file_path: Path,
        user_requirements: str | None = None,
        selected_suggestions: list[dict[str, Any]] | None = None,
    ) -> ProcessCleanFileResult | OperationFailedModel:
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
            analysis_result = await self.process_file(model_id, file_path, user_requirements)

            if is_failed(analysis_result):
                return analysis_result
            assert is_success(analysis_result)

            # 2. 如果没有指定选择的建议，使用所有自动应用的建议
            if selected_suggestions is None:
                selected_suggestions = [
                    suggestion
                    for suggestion in analysis_result.cleaning_suggestions
                    if suggestion.get("auto_apply", False)
                ]

            # 3. 应用用户选择的清洗操作（传递所选模型）
            cleaning_result = await self.apply_user_selected_cleaning(
                file_path=file_path,
                selected_suggestions=selected_suggestions,
                field_mappings=analysis_result.field_mappings,
                user_requirements=user_requirements,
                model_id=model_id,
            )

            if is_failed(cleaning_result):
                return cleaning_result

            assert is_success(cleaning_result)

            # 4. 合并结果
            return ProcessCleanFileResult(
                analysis_result=analysis_result,
                cleaning_result=cleaning_result,
                final_data=cleaning_result.cleaned_data,
                field_mappings=analysis_result.field_mappings,
                applied_operations=cleaning_result.applied_operations,
                summary=ProcessCleanFileSummary(
                    analysis=analysis_result.summary,
                    cleaning=cleaning_result.summary,
                ),
            )

        except Exception as err:
            logger.error(f"处理和清洗文件失败: {err}")
            return OperationFailedModel.from_err(err)

    async def process_file(
        self,
        model_id: str,
        file_path: Path,
        user_requirements: str | None = None,
    ) -> ProcessFileResult | OperationFailedModel:
        """处理数据文件的主要入口"""
        # 初始化状态
        initial_state = CleaningState(
            file_path=file_path,
            source_id=None,
            user_requirements=user_requirements,
            quality_issues=[],
            field_mappings={},
            cleaning_suggestions=[],
            cleaned_source_id=None,
            cleaning_summary="",
            error_message=None,
            model_id=model_id,
        )
        result = None

        try:
            # 执行工作流
            config = ensure_config({"configurable": {"thread_id": threading.get_ident()}})
            result = cast("CleaningState", await self._graph.ainvoke(initial_state, config))

            # 构建返回结果
            if error_message := result.get("error_message"):
                return OperationFailedModel(message=error_message, error_type="DataProcessingError")

            # 构建质量报告
            source = load_source(result, "source_id")
            df = await source.get_full_async()
            quality_report = DataQualityReport(
                overall_score=calculate_quality_score(result["quality_issues"]),
                total_rows=len(df),
                total_columns=len(df.columns),
                missing_values_count=int(df.isna().sum().sum()),
                duplicate_rows_count=int(df.duplicated().sum()),
                issues=result["quality_issues"],
                recommendations=[s.get("suggested_action", "") for s in result["cleaning_suggestions"]],
            )

            return ProcessFileResult(
                quality_report=quality_report,
                field_mappings=result["field_mappings"],
                cleaning_suggestions=result["cleaning_suggestions"],
                summary=result["cleaning_summary"],
            )

        except Exception as err:
            logger.error(f"处理文件失败: {err}")
            return OperationFailedModel.from_err(err)

        finally:
            if result is not None:
                if source_id := result.get("source_id"):
                    temp_source_service.delete(source_id)
                if cleaned_source_id := result.get("cleaned_source_id"):
                    temp_source_service.delete(cleaned_source_id)


# 创建全局实例
smart_clean_agent = SmartCleanDataAgent()
