import queue
import threading
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import TypedDict, cast

import pandas as pd
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.runnables import RunnableLambda, ensure_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from app.core.chain.llm import LLM
from app.core.executor import deserialize_result, serialize_result
from app.log import logger
from app.utils import format_overview, run_sync

from .tools import analyzer_tool, dataframe_tools

SYSTEM_PROMPT = """\
你是一位专业的数据分析师，擅长解决复杂的数据分析问题。请按照以下结构化方法分析数据：

1. 首先理解问题本质，确定分析目标
2. 设计分析步骤，将复杂问题拆解为可执行的子任务
3. 使用提供的工具进行数据处理和分析
4. 对结果进行解释，确保分析内容专业、准确且有洞见

## 工具使用指南
- 在一次分析中多次调用不同工具，构建完整分析流程
- 每次调用工具应解决一个明确的子任务
- 根据前一步执行的结果调整后续分析步骤
- 对于不同类型的任务，选择最合适的专用工具

## 特别注意
- analyze_data工具在Docker隔离环境中运行，其中对数据的修改不会反映到其他工具可访问的数据中
- 如需保留数据修改，必须使用create_column_tool等专用工具重新实现
- 对于特定任务，优先使用专用工具而非通用分析工具

## 数据概览
{overview}

## 工具选择指南
- **数据探索与可视化**：使用analyze_data工具进行灵活的探索性分析和可视化
- **数据处理与特征工程**：
  - create_column_tool：创建新列或转换现有列
  - create_interaction_term_tool：创建特征交互项
  - create_aggregated_feature_tool：创建基于分组聚合的特征
- **数据分析**：
  - correlation_analysis_tool：分析变量间相关性
  - lag_analysis_tool：分析时间序列数据中的时滞关系
  - detect_outliers_tool：检测异常值
- **特征选择**：
  - select_features_tool：自动选择最重要的特征子集
  - analyze_feature_importance_tool：分析特征重要性
- **模型训练与优化**：
  - optimize_hyperparameters_tool：优化模型超参数
  - plot_learning_curve_tool：评估模型性能随训练样本量的变化
  - train_model_tool：训练机器学习模型
  - evaluate_model_tool：评估模型性能
  - save_model_tool：保存训练好的模型

## 推荐分析流程
1. **数据探索**：使用analyze_data工具探索数据分布、缺失值等基本情况
2. **数据处理**：使用create_column_tool处理缺失值、异常值，创建新特征
3. **特征工程**：使用create_interaction_term_tool、create_aggregated_feature_tool构建高级特征
4. **特征分析与选择**：使用analyze_feature_importance_tool分析特征重要性，使用select_features_tool选择最佳特征子集
5. **模型训练与优化**：
   - 先使用optimize_hyperparameters_tool寻找最佳超参数
   - 使用plot_learning_curve_tool诊断模型偏差/方差问题
   - 使用train_model_tool训练最终模型，并传入优化后的超参数
   - 使用evaluate_model_tool评估模型性能
6. **结果解释与总结**：分析模型结果，提出洞见和建议

## 输出格式要求
- 分析报告应该结构清晰，包含标题、小节和结论
- 每个分析步骤都应包含工具调用结果和专业解释
- 对重要发现进行高亮说明
- 提供明确的结论和建议
- 当生成图表时，在解释中明确引用图表内容

请记住，通常需要多个连续的工具调用和结果解释才能得到全面而深入的分析。
"""


class AgentValues(TypedDict):
    messages: list[AnyMessage]


class AgentState(BaseModel):
    values: AgentValues
    results: list[tuple[str, dict]]


class DataAnalyzerAgent:
    def __init__(
        self,
        df: pd.DataFrame,
        llm: LLM,
        chat_model: BaseChatModel,
        *,
        pre_model_hook: RunnableLambda | None = None,
    ) -> None:
        analyzer, results = analyzer_tool(df, llm)
        df_tools, models, model_paths = dataframe_tools(df)

        self.agent = create_react_agent(
            model=chat_model,
            tools=[analyzer, *df_tools],
            prompt=SYSTEM_PROMPT.format(overview=format_overview(df)),
            checkpointer=InMemorySaver(),
            pre_model_hook=pre_model_hook,
            post_model_hook=self._post_model_hook,
        )
        self.config = ensure_config(
            {
                "recursion_limit": 200,
                "configurable": {"thread_id": threading.get_ident()},
            }
        )
        self.execution_results = results
        self.trained_models = models
        self.saved_model_paths = model_paths

        self.message_queue: queue.Queue[AIMessage] = queue.Queue()

    def load_state(self, state_file: Path) -> None:
        """从指定的状态文件加载 agent 状态。"""
        if not state_file.exists():
            return

        try:
            state = AgentState.model_validate_json(state_file.read_bytes())
        except ValueError:
            logger.warning("无法加载 agent 状态: 状态文件格式错误")
            return

        self.agent.update_state(self.config, state.values)
        self.execution_results[:] = [(query, deserialize_result(result)) for query, result in state.results]
        logger.info(f"已加载 agent 状态: {len(state.values['messages'])}")  # noqa: PD011

    def save_state(self, state_file: Path) -> None:
        """将当前 agent 状态保存到指定的状态文件。"""
        state = AgentState(
            values=cast("AgentValues", self.agent.get_state(self.config).values),
            results=[(query, serialize_result(result)) for query, result in self.execution_results],
        )
        state_file.write_bytes(state.model_dump_json().encode("utf-8"))
        logger.info(f"已保存 agent 状态: {len(state.values['messages'])}")  # noqa: PD011

    def invoke(self, user_input: str) -> Generator[AIMessage]:
        """使用用户输入调用 agent"""

        def invoke() -> None:
            self.agent.invoke({"messages": [{"role": "user", "content": user_input}]}, self.config)
            finished.set()

        finished = threading.Event()
        invoke_thread = threading.Thread(target=invoke)
        invoke_thread.start()

        while not finished.is_set():
            try:
                message = self.message_queue.get(timeout=1)
                if isinstance(message, AIMessage):
                    yield message
            except queue.Empty:
                continue

        invoke_thread.join()

    async def ainvoke(self, user_input: str) -> AsyncGenerator[AIMessage]:
        """异步使用用户输入调用 agent"""
        gen = self.invoke(user_input)
        step = run_sync(lambda: next(gen, None))

        while message := await step():
            if isinstance(message, AIMessage):
                yield message

    def _post_model_hook(self, state: dict) -> dict:
        messages = state.get("messages", [])
        self.message_queue.put(messages[-1])
        return {}
