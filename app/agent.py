import threading
from pathlib import Path
from typing import TypedDict, cast

import pandas as pd
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.runnables import RunnableLambda, ensure_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, TypeAdapter

from app.agent_tools.analyzer import analyzer_tool
from app.agent_tools.dataframe import dataframe_tools
from app.chain.llm import LLM
from app.executor import deserialize_result, serialize_result
from app.log import logger
from app.utils import format_overview

SYSTEM_PROMPT = """\
你是一位专业的数据分析师，擅长解决复杂的数据分析问题。请按照以下结构化方法分析数据：

1. 首先理解问题本质，确定分析目标
2. 设计分析步骤，将复杂问题拆解为可执行的子任务
3. 使用提供的工具进行数据处理和分析
4. 对结果进行解释，确保分析内容专业、准确且有洞见

## 工具使用指南
- 你可以且应该在一次分析中多次调用工具
- 每次调用工具应解决一个明确的子任务，如数据探索、清洗、可视化等
- 根据前一步执行的结果调整后续分析步骤
- 避免在单次工具调用中完成所有分析任务，这通常会导致错误或不完整的结果

## 数据概览
{overview}

## 分析方法指南
- 数据清洗: 处理缺失值、异常值和重复数据
- 描述性统计: 计算均值、中位数、分布等基本统计量
- 可视化分析: 使用合适的图表展示数据分布和关系(生成的图表将直接展示给用户)
- 相关性分析: 探索变量之间的相互关系
- 时序分析: 对时间序列数据进行趋势和模式识别
- 聚类分析: 识别数据中的自然分组
- 异常检测: 使用统计方法或机器学习识别异常值

## 多步分析示例流程
1. 第一次调用工具：探索数据基本结构和统计特征
2. 第二次调用工具：针对发现的问题进行数据清洗
3. 第三次调用工具：对清洗后的数据进行可视化分析
4. 第四次调用工具：应用特定的分析方法（如相关性分析）
5. 最后总结所有步骤的发现和结论

## 输出格式要求
- 分析报告应该结构清晰，包含标题、小节和结论
- 每个分析步骤都应包含代码、结果和解释
- 明确标注每个工具调用的目的和预期结果
- 对重要发现进行高亮说明
- 提供明确的结论和建议

在分析过程中始终记住，复杂的分析问题通常需要多个连续的工具调用才能得到全面而深入的解答。
"""


class AgentValues(TypedDict):
    messages: list[AnyMessage]


class AgentState(BaseModel):
    values: AgentValues
    results: list[tuple[str, dict]]


state_ta = TypeAdapter(AgentState)


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

    def load_state(self, state_file: Path) -> None:
        """从指定的状态文件加载 agent 状态。"""
        if state_file.exists():
            try:
                state = state_ta.validate_json(state_file.read_bytes())
            except ValueError:
                logger.warning("无法加载 agent 状态: 状态文件格式错误")
            else:
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

    def invoke(self, user_input: str) -> AIMessage:
        """使用用户输入调用 agent，并返回最后一条 AI 消息。"""
        result = self.agent.invoke({"messages": [{"role": "user", "content": user_input}]}, self.config)
        message: AIMessage = result["messages"][-1]
        logger.info(f"LLM 输出:\n{message.content}")
        return message
