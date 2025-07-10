import functools
import threading
from collections.abc import AsyncIterator, Iterator
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
from app.core.datasource import DataSource
from app.log import logger
from app.utils import escape_tag, format_overview

from .events import BufferedStreamEventReader, StreamEvent
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
  - create_model_tool：创建机器学习模型实例（不训练）
  - fit_model_tool：训练已创建的模型
  - create_composite_model_tool：创建集成模型，组合多个已训练模型
  - optimize_hyperparameters_tool：优化模型超参数
  - plot_learning_curve_tool：评估模型性能随训练样本量的变化
  - evaluate_model_tool：评估模型性能
  - save_model_tool：保存训练好的模型
  - load_model_tool：加载已保存的模型

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
   - 特征工程后，使用inspect_dataframe_tool检查处理后的数据结果

7. **模型构建(如需)**：
   - 使用analyze_feature_importance_tool分析特征重要性
   - 使用select_features_tool选择最佳特征子集
   - 使用create_model_tool创建模型，然后使用fit_model_tool训练
   - 使用create_composite_model_tool组合多个模型创建更强的集成模型
   - 使用evaluate_model_tool评估模型性能

8. **结果可视化与解释**：
   - 创建关键发现的直观图表
   - 将分析结果与业务问题关联
   - 提供明确的数据洞察和行动建议
   - 总结分析局限性和未来分析方向

## 数据准备与模型训练工作流

**从数据到模型的完整流程**：
1. 使用inspect_dataframe_tool全面了解数据
2. 使用correlation_analysis_tool、detect_outliers_tool等分析数据特性
3. 使用create_column_tool等工具进行数据清洗和特征工程
4. 使用select_features_tool和analyze_feature_importance_tool选择最佳特征
5. 创建并训练模型（使用create_model_tool和fit_model_tool）
6. 评估和优化模型性能

**特征工程最佳实践**：
- 使用create_column_tool处理缺失值和异常值
- 使用create_interaction_term_tool捕捉特征间的相互影响
- 使用create_aggregated_feature_tool从分组数据中提取模式
- 每次创建新特征后，使用inspect_dataframe_tool检查结果
- 使用analyze_feature_importance_tool评估新特征的价值

## 模型构建工作流

**分步式模型开发流程**：
1. 使用create_model_tool创建模型实例（获取model_id）
2. 使用fit_model_tool训练模型（使用model_id）
3. 使用evaluate_model_tool评估模型性能
4. 使用save_model_tool保存表现良好的模型

**优化模型超参数**：
- 可以使用optimize_hyperparameters_tool来寻找单个模型的最佳超参数
- 各模型训练完成后，可以通过create_composite_model_tool的weights参数调整集成模型中各基础模型的权重
- 例如，设置weights=[0.7, 0.3]表示第一个模型权重为0.7，第二个模型权重为0.3

**集成模型构建流程**：
1. 先使用optimize_hyperparameters_tool优化每个基础模型的超参数
2. 使用优化后的超参数创建并训练多个基础模型
3. 评估每个基础模型的性能
4. 根据性能评估结果确定权重，例如：基于准确率的相对比例
5. 使用create_composite_model_tool和指定的weights创建集成模型

**模型改进建议**：
- 使用optimize_hyperparameters_tool优化模型超参数
- 使用plot_learning_curve_tool诊断模型是否存在过拟合问题
- 使用select_features_tool选择最相关的特征子集
- 尝试不同类型的模型并比较性能

**集成模型构建伪代码示例**：
<code>
# 1. 优化基础模型超参数
rf_params_result = optimize_hyperparameters_tool(
    features=["feature1", "feature2"],
    target="target",
    model_type="random_forest_classifier"
)
gb_params_result = optimize_hyperparameters_tool(
    features=["feature1", "feature2"],
    target="target",
    model_type="gradient_boosting_classifier"
)

# 2. 使用优化后的超参数训练基础模型
rf_model_id = create_model_tool(
    model_type="random_forest_classifier",
    hyperparams=rf_params_result["best_params"]
)
rf_trained_id = fit_model_tool(
    model_id=rf_model_id,
    features=["feature1", "feature2"],
    target="target"
)

gb_model_id = create_model_tool(
    model_type="gradient_boosting_classifier",
    hyperparams=gb_params_result["best_params"]
)
gb_trained_id = fit_model_tool(
    model_id=gb_model_id,
    features=["feature1", "feature2"],
    target="target"
)

# 3. 评估各模型性能
rf_eval = evaluate_model_tool(rf_trained_id)
gb_eval = evaluate_model_tool(gb_trained_id)

# 4. 根据性能确定权重
rf_acc = rf_eval["metrics"]["accuracy"]
gb_acc = gb_eval["metrics"]["accuracy"]
total_acc = rf_acc + gb_acc
rf_weight = rf_acc / total_acc
gb_weight = gb_acc / total_acc

# 5. 创建集成模型，指定权重
ensemble_id = create_composite_model_tool(
    model_ids=[rf_trained_id, gb_trained_id],
    weights=[rf_weight, gb_weight],
    voting="soft"
)

# 6. 评估集成模型
ensemble_eval = evaluate_model_tool(ensemble_id)
</code>

### 主动优化指导
当用户要求优化模型性能时，请主动采取以下步骤：
1. **探索多种特征组合**：尝试不同的特征子集，如高相关性特征、主成分分析选择的特征
2. **超参数优化**：对每个模型使用optimize_hyperparameters_tool寻找最佳参数，解释不同参数的影响
3. **尝试多种模型类型**：至少测试3种不同的模型类型并比较性能，说明各模型的优缺点
4. **创建集成模型**：基于单模型性能结果，设置合理的权重构建集成模型
5. **完整报告比较**：对比所有模型(包括不同参数配置)的性能指标，提供明确的推荐和理由

## 主动分析指导
在完成每个分析阶段后，主动向用户提出下一步建议：

1. **数据探索阶段后**：
   - 指出数据中可能的异常模式或值得深入研究的关系
   - 建议特定变量的转换方法（如对偏态分布进行对数转换）
   - 提出需要进一步清理的数据质量问题

2. **相关性分析后**：
   - 推荐值得探索的变量组合
   - 提出可能的因果关系假设
   - 建议创建的交互特征

3. **特征工程后**：
   - 评估新特征的潜在价值
   - 建议进一步的特征变换或选择
   - 推荐最有可能提高分析质量的特征子集

4. **初步分析结果后**：
   - 提出验证初步发现的方法
   - 建议更深入的分析方向
   - 指出可能被忽略的数据视角

5. **整体分析完成后**：
   - 总结主要发现和局限性
   - 提出3-5个明确的后续步骤建议
   - 指出哪些问题仍未解答以及如何进一步探索

无论用户是否明确要求，在每次分析结束时，主动提供一个"下一步建议"部分，包含3-5个具体、可操作的建议，帮助用户进一步提升分析质量或模型性能。
格式如下：
**下一步建议**（只输出如下格式，便于前端提取）：
1.建议1内容
2.建议2内容
3.建议3内容
4.建议4内容

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
            logger.opt(colors=True).info(
                f"恢复工具调用: <y>{escape_tag(call['name'])}</> - {escape_tag(str(call['args']))}"
            )
            try:
                result = tool(df=df, **call["args"])
            except Exception as err:
                logger.opt(colors=True, exception=True).warning(
                    f"工具调用恢复失败: <y>{escape_tag(call['name'])}</> - {escape_tag(str(err))}"
                )
                return original
            if not result["success"]:
                logger.opt(colors=True).warning(
                    f"工具调用恢复失败: <y>{escape_tag(call['name'])}</> - {escape_tag(result['message'])}"
                )
                return original

    return df


class DataAnalyzerAgent:
    def __init__(
        self,
        data_source: DataSource,
        llm: LLM,
        chat_model: BaseChatModel,
        *,
        pre_model_hook: RunnableLambda | None = None,
    ) -> None:
        self.data_source = data_source
        analyzer = analyzer_tool(data_source, llm)
        df_tools = dataframe_tools(data_source.get_full)
        
        # 创建agent引用函数
        def get_agent():
            return self
        
        sk_tools, models, saved_models = scikit_tools(data_source.get_full, get_agent)

        self.agent = create_react_agent(
            model=chat_model,
            tools=[analyzer, *df_tools, *sk_tools],
            prompt=SYSTEM_PROMPT.format(overview=format_overview(data_source.get_preview())),
            checkpointer=InMemorySaver(),
            pre_model_hook=pre_model_hook,
        )
        self.config = ensure_config(
            {
                "recursion_limit": 200,
                "configurable": {"thread_id": threading.get_ident()},
            }
        )
        self.trained_models = models
        self.saved_models = saved_models
        self._first_user_message = None  # 存储用户第一次提问的内容

    def get_first_user_message(self) -> str | None:
        """获取用户第一次提问的内容"""
        if self._first_user_message is not None:
            return self._first_user_message
        
        # 从agent状态中获取消息历史
        try:
            state = self.agent.get_state(self.config)
            messages = state.values.get("messages", [])
            
            # 查找第一条用户消息
            for message in messages:
                if hasattr(message, 'type') and message.type == 'human':
                    self._first_user_message = message.content
                    return self._first_user_message
                elif hasattr(message, 'role') and message.role == 'user':
                    self._first_user_message = message.content
                    return self._first_user_message
        except Exception:
            pass
        
        return None

    def set_first_user_message(self, message: str) -> None:
        """设置用户第一次提问的内容"""
        if self._first_user_message is None:
            self._first_user_message = message

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
        self.saved_models.update(state.models)
        self.data_source.set_full_data(resume_tool_calls(self.data_source.get_full(), values["messages"]))
        logger.opt(colors=True).info(f"已加载 agent 状态: <y>{len(values['messages'])}</>")

    def save_state(self, state_file: Path) -> None:
        """将当前 agent 状态保存到指定的状态文件。"""
        state = AgentState(
            values=cast("AgentValues", self.agent.get_state(self.config).values),
            models=self.saved_models,
        )
        state_file.write_bytes(state.model_dump_json().encode("utf-8"))
        logger.opt(colors=True).info(f"已保存 agent 状态: <y>{len(state.values['messages'])}</>")  # noqa: PD011

    def stream(self, user_input: str) -> Iterator[StreamEvent]:
        """使用用户输入调用 agent，并以流式方式返回事件"""
        # 如果是第一次调用，设置用户消息
        self.set_first_user_message(user_input)
        
        reader = BufferedStreamEventReader()

        for event in self.agent.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config,
            stream_mode="messages",
        ):
            yield from reader.push(event)
        if evt := reader.flush():
            yield evt

    async def astream(self, user_input: str) -> AsyncIterator[StreamEvent]:
        """异步使用用户输入调用 agent，并以流式方式返回事件"""
        # 如果是第一次调用，设置用户消息
        self.set_first_user_message(user_input)
        
        reader = BufferedStreamEventReader()

        async for event in self.agent.astream(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config,
            stream_mode="messages",
        ):
            for evt in reader.push(event):
                yield evt
        if evt := reader.flush():
            yield evt
