import functools
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

from .tools import analyzer_tool, dataframe_tools, scikit_tools
from .tools.dataframe.columns import create_aggregated_feature, create_column, create_interaction_term

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
- **数据探索与可视化**：
  - analyze_data工具：进行灵活的探索性分析和可视化
  - inspect_dataframe_tool：查看当前数据框状态，尤其是在数据修改后
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
1. **数据理解与目标明确**：
   - 确定分析目标和关键问题
   - 了解数据背景和业务含义
   - 明确分析指标和预期结果

2. **数据探索与描述统计**：
   - 使用analyze_data工具全面了解数据分布、缺失值、基本统计量
   - 分析各变量类型、取值范围和统计特征
   - 识别潜在的数据质量问题

3. **数据清理与预处理**：
   - 使用create_column_tool处理缺失值、异常值
   - 标准化/归一化数值特征
   - 编码分类变量
   - 处理日期时间数据

4. **探索性数据分析**：
   - 使用correlation_analysis_tool分析变量间相关关系
   - 使用detect_outliers_tool识别并处理异常值
   - 分析数据分布和趋势
   - 探索关键变量的时间模式(如适用)

5. **高级分析与假设验证**：
   - 进行分组比较分析
   - 假设检验和统计推断
   - 识别关键影响因素
   - 使用lag_analysis_tool分析时序关系(如适用)

6. **特征工程与数据转换**：
   - 使用create_interaction_term_tool创建特征交互项
   - 使用create_aggregated_feature_tool创建聚合特征
   - 构建业务相关的派生指标

7. **模型构建(如需)**：
   - 使用analyze_feature_importance_tool分析特征重要性
   - 使用select_features_tool选择最佳特征子集
   - 使用train_model_tool训练预测或分类模型
   - 使用evaluate_model_tool评估模型性能

8. **结果可视化与解释**：
   - 创建关键发现的直观图表
   - 将分析结果与业务问题关联
   - 提供明确的数据洞察和行动建议
   - 总结分析局限性和未来分析方向

## 模型使用工作流示例

**训练-评估-保存流程**：
1. 使用 train_model_tool 训练模型，得到 trained_model_id
2. 使用 evaluate_model_tool 评估该模型
3. 使用 save_model_tool 保存模型供未来使用

**加载-评估流程**：
1. 使用 load_model_tool 加载之前保存的模型，得到 trained_model_id
2. 使用 evaluate_model_tool 直接评估加载的模型（无需重新训练）

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
    models: dict[str, Path]


TOOLS_TO_RESUME = {
    "create_column_tool": create_column,
    "create_interaction_term_tool": create_interaction_term,
    "create_aggregated_feature_tool": create_aggregated_feature,
}


def resume_tool_calls(df: pd.DataFrame, messages: list[AnyMessage]) -> pd.DataFrame:
    original = df.copy()
    for call in functools.reduce(
        (lambda a, b: a + b),
        (m.tool_calls for m in messages if isinstance(m, AIMessage) and m.tool_calls),
    ):
        if tool := next((tool for name, tool in TOOLS_TO_RESUME.items() if name in call["name"]), None):
            logger.info(f"恢复工具调用: {call['name']} - {call['args']}")
            try:
                result = tool(df=df, **call["args"])
            except Exception as err:
                logger.warning(f"工具调用恢复失败: {call['name']} - {err}")
                return original
            if not result["success"]:
                logger.warning(f"工具调用恢复失败: {call['name']} - {result['message']}")
                return original

    return df


class DataAnalyzerAgent:
    def __init__(
        self,
        df: pd.DataFrame,
        llm: LLM,
        chat_model: BaseChatModel,
        *,
        pre_model_hook: RunnableLambda | None = None,
    ) -> None:
        self.df = df
        analyzer, results = analyzer_tool(df, llm)
        df_tools = dataframe_tools(lambda: self.df)
        sk_tools, models, saved_models = scikit_tools(lambda: self.df)

        self.agent = create_react_agent(
            model=chat_model,
            tools=[analyzer, *df_tools, *sk_tools],
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
        self.saved_models = saved_models

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

        values = state.values  # noqa: PD011
        self.agent.update_state(self.config, values)
        self.execution_results[:] = [(query, deserialize_result(result)) for query, result in state.results]
        self.saved_models.update(state.models)
        self.df = resume_tool_calls(self.df, values["messages"])
        logger.info(f"已加载 agent 状态: {len(values['messages'])}")

    def save_state(self, state_file: Path) -> None:
        """将当前 agent 状态保存到指定的状态文件。"""
        state = AgentState(
            values=cast("AgentValues", self.agent.get_state(self.config).values),
            results=[(query, serialize_result(result)) for query, result in self.execution_results],
            models=self.saved_models,
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
