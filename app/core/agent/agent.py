import functools
import threading
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableLambda, ensure_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from app.core.agent.events import StreamEvent, fix_message_content, process_stream_event
from app.core.agent.schemas import (
    AgentValues,
    DataAnalyzerAgentState,
    DatasetID,
    Sources,
    format_sources_overview,
    sources_fn,
)
from app.core.agent.tools import analyzer_tool, dataframe_tools, scikit_tools, sources_tools
from app.core.agent.tools.dataframe.columns import create_aggregated_feature, create_column, create_interaction_term
from app.core.chain.llm import LLM
from app.log import logger
from app.utils import escape_tag

TOOL_INTRO = """\
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
- **多数据集操作**：
  - join_dataframes_tool：连接两个数据集（类似SQL JOIN）
  - combine_dataframes_tool：执行多个数据集的集合操作（并集、交集、差集）
  - create_dataset_from_query_tool：通过查询从现有数据集创建新数据集
  - create_dataset_by_sampling_tool：通过采样从现有数据集创建新数据集
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
  - predict_with_model_tool：使用训练好的模型进行预测
  - save_model_tool：保存训练好的模型
  - load_model_tool：加载已保存的模型
"""

SYSTEM_PROMPT = """\
你是一位专业的数据分析师，擅长解决复杂的数据分析问题。

## 重要提示：请始终使用中文回答用户的问题，严禁使用英文回答。

请按照以下结构化方法分析数据：

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
{tool_intro}

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

4. **多数据集处理(如适用)**：
   - 使用join_dataframes_tool连接相关数据集
   - 使用combine_dataframes_tool执行数据集的集合操作
   - 使用create_dataset_from_query_tool或create_dataset_by_sampling_tool创建分析子集

5. **探索性数据分析**：
   - 使用correlation_analysis_tool分析变量间相关关系
   - 使用detect_outliers_tool识别并处理异常值
   - 分析数据分布和趋势
   - 探索关键变量的时间模式(如适用)

6. **高级分析与假设验证**：
   - 进行分组比较分析
   - 假设检验和统计推断
   - 识别关键影响因素
   - 使用lag_analysis_tool分析时序关系(如适用)

7. **特征工程与数据转换**：
   - 使用create_interaction_term_tool创建特征交互项
   - 使用create_aggregated_feature_tool创建聚合特征
   - 构建业务相关的派生指标
   - 特征工程后，使用inspect_dataframe_tool检查处理后的数据结果

8. **模型构建(如需)**：
   - 使用analyze_feature_importance_tool分析特征重要性
   - 使用select_features_tool选择最佳特征子集
   - 使用create_model_tool创建模型，然后使用fit_model_tool训练
   - 使用create_composite_model_tool组合多个模型创建更强的集成模型
   - 使用evaluate_model_tool评估模型性能

9. **结果可视化与解释**：
   - 创建关键发现的直观图表
   - 将分析结果与业务问题关联
   - 提供明确的数据洞察和行动建议
   - 总结分析局限性和未来分析方向

## 数据准备与模型训练工作流

**从数据到模型的完整流程**：
1. 使用inspect_dataframe_tool全面了解数据
2. 使用correlation_analysis_tool、detect_outliers_tool等分析数据特性
3. 使用create_column_tool等工具进行数据清洗和特征工程
4. 需要时，使用join_dataframes_tool或combine_dataframes_tool整合多个数据源
5. 使用select_features_tool和analyze_feature_importance_tool选择最佳特征
6. 创建并训练模型（使用create_model_tool和fit_model_tool）
7. 评估和优化模型性能

## 多数据集操作最佳实践

**数据集连接策略**：
- 使用join_dataframes_tool连接相关数据集，类似SQL JOIN操作
- 根据业务需求选择适当的连接类型（内连接、左连接、右连接、全连接）
- 确保连接键的数据类型一致，避免类型不匹配导致的连接问题

**数据集集合操作**：
- 使用combine_dataframes_tool执行并集、交集、差集等集合操作
- 根据列结构决定是否需要匹配列（match_columns参数）
- 当进行交集或差集操作时，注意观察结果集的大小变化

**数据集派生**：
- 使用create_dataset_from_query_tool基于条件筛选创建分析子集
- 使用create_dataset_by_sampling_tool创建训练集、测试集或验证集
- 分层采样（stratify_by参数）有助于保持目标变量分布

**多数据集工作流示例**：
<code>
# 1. 检查原始数据集
main_data_info = inspect_dataframe_tool(dataset_id="main_data")

# 2. 连接辅助数据集
joined_data_result = join_dataframes_tool(
    left_dataset_id="main_data",
    right_dataset_id="reference_data",
    join_type="left",
    left_on="customer_id",
    right_on="id"
)

# 3. 从连接结果创建分析子集
analysis_subset_result = create_dataset_from_query_tool(
    dataset_id=joined_data_result["new_dataset_id"],
    query="purchase_amount > 100 and customer_type == 'premium'"
)

# 4. 创建训练集和测试集
train_data_result = create_dataset_by_sampling_tool(
    dataset_id=analysis_subset_result["new_dataset_id"],
    frac=0.7,
    stratify_by="target_variable",
    random_state=42
)

test_data_result = create_dataset_from_query_tool(
    dataset_id=analysis_subset_result["new_dataset_id"],
    query=f"index not in {{train_data_result['creation_details']['sampled_indices']}}"
)
</code>

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

**预测与应用工作流**：
1. 使用fit_model_tool训练模型或load_model_tool加载模型
2. 使用evaluate_model_tool评估模型性能
3. 使用predict_with_model_tool对新数据进行预测
4. 分析预测结果，提取关键见解

**模型预测工作流示例**：
<code>
# 1. 训练或加载模型
model_id = create_model_tool(
    model_type="random_forest_classifier",
    hyperparams={{"n_estimators": 100, "max_depth": 10}}
)
trained_model_id = fit_model_tool(
    model_id=model_id,
    features=["feature1", "feature2", "feature3"],
    target="target_variable"
)

# 2. 评估模型性能
evaluation = evaluate_model_tool(trained_model_id)
print(f"模型准确率: {{evaluation['metrics']['accuracy']}}")

# 3. 使用模型进行预测
prediction_result = predict_with_model_tool(
    dataset_id="test_data",  # 包含新数据的数据集
    model_id=trained_model_id,
    input_features=["feature1", "feature2", "feature3"]  # 可选，默认使用训练时的特征
)

# 4. 分析预测结果
prediction_dataset_id = prediction_result["prediction_dataset_id"]
predictions_info = inspect_dataframe_tool(
    dataset_id=prediction_dataset_id,
    options={{
        "n_rows_preview": 10,
        "show_summary_stats": True
    }}
)
</code>

**预测结果解释最佳实践**：
- 解释预测分布的特点（如均值、分位数、极值）
- 识别异常预测并分析可能原因
- 将预测结果与实际观察值对比（如有）
- 针对分类问题，分析各类别的预测比例
- 针对回归问题，评估预测值的范围是否符合业务逻辑

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

无论用户是否明确要求，在每次分析结束时，你必须提供一个格式如下的"下一步建议"部分（便于前端提取）：

**下一步建议**：
1. 建议1内容
2. 建议2内容
3. 建议3内容
4. [可选] 建议4内容
5. [可选] 建议5内容

## 输出格式要求
- 分析报告应该结构清晰，包含标题、小节和结论
- 每个分析步骤都应包含工具调用结果和专业解释
- 对重要发现进行高亮说明
- 提供明确的结论和建议
- 当生成图表时，在解释中明确引用图表内容

请记住，通常需要多个连续的工具调用和结果解释才能得到全面而深入的分析。
"""

CREATE_TITLE_PROMPT = """\
你是一位专业的数据分析对话总结专家。

## 重要提示：请始终使用中文生成标题，严禁使用英文。

请根据以下用户与AI数据分析师之间的对话内容，生成一个简洁、准确且信息丰富的会话标题。

## 指导原则：
1. 标题应体现用户的主要分析需求或问题
2. 标题应包含数据分析的核心主题或目标
3. 标题长度应控制在5-10个字之间，最多不超过15个字
4. 使用专业且精确的术语
5. 不要使用"分析""研究"等过于笼统的词语开头
6. 直接给出标题，不要有多余的解释或引导语

## 格式要求：
- 仅输出标题文本，不需要引号或其他标点符号
- 不要包含"标题："、"会话标题："等前缀

## 对话记录：
{conversation}

请基于以上对话记录生成一个适合的标题：
"""

SUMMARY_PROMPT = """\
你是一位专业的数据分析总结专家。

## 重要提示：请始终使用中文生成分析总结报告，严禁使用英文。

请根据以下用户与AI数据分析师之间的对话内容，生成一份结构清晰的分析总结报告。

## 报告要求：
1. 报告应包含以下主要部分：
   - 分析目标：用户希望解决的核心问题或达成的分析目标
   - 数据概述：简要描述分析中使用的数据特点
   - 分析过程：按时间顺序概括主要分析步骤和使用的方法
   - 关键发现：列出分析中发现的最重要见解
   - 结论与建议：总结分析结果并提出后续行动建议

2. 报告风格要求：
   - 专业、简洁、客观
   - 重点突出关键分析步骤和结果
   - 使用专业术语，但避免过于技术性的细节描述
   - 保持结构清晰，使用小标题和要点列表增强可读性
   - 避免直接提及工具ID，而是描述执行的操作（如"进行了相关性分析"而非"使用correlation_analysis_tool"）

## 数据分析工具说明：
{tool_intro}

## 数据分析过程概括指南：
1. 识别并总结用户进行的主要数据探索步骤
2. 提取使用的关键分析方法（如相关性分析、特征工程、模型训练等）
3. 总结每个主要分析阶段的结果和见解
4. 忽略技术实现细节，保留业务洞察和数据见解

## 关键发现提取指南：
1. 识别对话中提到的显著模式、关联或趋势
2. 提取统计上显著的结果
3. 包括可能影响业务决策的重要发现
4. 关注预测模型（如有）的性能和关键影响因素

## 结论与建议部分指南：
1. 综合分析结果回答用户的初始问题
2. 提出3-5条基于数据支持的具体建议
3. 指出分析的局限性和可能的改进方向
4. 建议可能的后续分析方向

## 图表引用指南：
1. 在对话中出现的图表将使用ID标识 (例如：[包含图片输出, ID=0])
2. 在报告中需要引用图表时，使用以下格式：![图表描述]({{figure-0}})
3. 图表ID从0开始编号，按照在对话中出现的顺序递增
4. 图表描述应简明扼要地说明图表内容和目的
5. 在引用图表的同时，务必在正文中对图表内容进行解释和分析

## 图表引用示例：
- "从相关性分析结果可以看出，特征A和目标变量呈强正相关，如下图所示：![特征A与目标变量的相关性热图]({{figure-0}})"
- "下图展示了各特征的重要性排序，其中特征B最为重要：![特征重要性排序]({{figure-2}})"

## 输出格式要求：
- 使用Markdown格式输出报告
- 正确引用并解释相关图表
- 使用标题和小标题组织报告结构
- 使用列表条目增强关键发现和建议的可读性
- 描述数据分析步骤时使用专业术语（如"进行特征选择"、"执行异常值检测"），而非提及具体工具名称
- 尽量用业务语言而非技术语言描述结果，使非技术人员也能理解

## 对话记录：
{conversation}

请根据以上对话记录生成分析总结报告：
"""


TOOLS_TO_RESUME = {
    "create_column_tool": create_column,
    "create_interaction_term_tool": create_interaction_term,
    "create_aggregated_feature_tool": create_aggregated_feature,
}


def resume_tool_calls(sources: Sources, messages: list[AnyMessage]) -> None:
    all_tool_calls = functools.reduce(
        (lambda a, b: a + b),
        (m.tool_calls for m in messages if isinstance(m, AIMessage) and m.tool_calls),
    )

    if not all_tool_calls:
        return

    for call in all_tool_calls:
        if tool := next((tool for name, tool in TOOLS_TO_RESUME.items() if name in call["name"]), None):
            logger.opt(colors=True).info(
                f"恢复工具调用: <y>{escape_tag(call['name'])}</> - {escape_tag(str(call['args']))}"
            )
            try:
                dataset_id = cast("DatasetID", call["args"]["dataset_id"])
                result = tool(df=sources[dataset_id].get_full(), **call["args"])
            except Exception as err:
                logger.opt(colors=True, exception=True).warning(
                    f"工具调用恢复失败: <y>{escape_tag(call['name'])}</> - {escape_tag(str(err))}"
                )
                continue
            if not result["success"]:
                logger.opt(colors=True).warning(
                    f"工具调用恢复失败: <y>{escape_tag(call['name'])}</> - {escape_tag(result['message'])}"
                )


def format_conversation(messages: list[AnyMessage], *, include_figures: bool) -> tuple[str, list[str]]:
    """格式化对话记录为字符串"""
    formatted: list[str] = []
    figures: list[str] = []
    for message in messages:
        match message:
            case HumanMessage(content=content):
                formatted.append(f"用户:\n<user-content>\n{content}\n</user-content>")
            case AIMessage(content=content, tool_calls=tool_calls):
                content = fix_message_content(content)
                formatted.append(f"AI:\n<ai-content>\n{content}\n</ai-content>")
                for tool_call in tool_calls:
                    if tool_call["id"] is None:
                        continue
                    formatted.append(
                        f"工具调用请求({tool_call['id']}): {tool_call['name']}\n"
                        f"<tool-call-args>\n{tool_call['args']!r}\n</tool-call-args>"
                    )
            case ToolMessage(tool_call_id=id, status=status, content=content, artifact=artifact):
                artifact_info = ""
                if (
                    include_figures
                    and isinstance(artifact, dict)
                    and artifact.get("type") == "image"
                    and (base64_data := artifact.get("base64_data")) is not None
                ):
                    artifact_info = f"[包含图片输出, ID={len(figures)}]\n"
                    figures.append(base64_data)
                formatted.append(f"工具调用结果({id}): {status}\n<tool-call>\n{content!r}\n{artifact_info}</tool-call>")

    return f"<conversation>\n{'\n'.join(formatted) if formatted else '无对话记录'}\n</conversation>", figures


def _create_title_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[object, str]:
    input = {"conversation": format_conversation(messages, include_figures=False)[0]}
    prompt = PromptTemplate(template=CREATE_TITLE_PROMPT, input_variables=["conversation"])
    return (lambda _: input) | prompt | llm


def _summary_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[object, tuple[str, list[str]]]:
    conversation, figures = format_conversation(messages, include_figures=True)
    prompt = PromptTemplate(template=SUMMARY_PROMPT, input_variables=["conversation", "tool_intro"])
    params = {"conversation": conversation, "tool_intro": TOOL_INTRO}
    return (lambda _: params) | prompt | llm | (lambda s: (s, figures))


class DataAnalyzerAgent:
    def __init__(
        self,
        sources: Sources,
        llm: LLM,
        chat_model: BaseChatModel,
        session_id: str,
        *,
        pre_model_hook: RunnableLambda | None = None,
    ) -> None:
        self.sources = sources
        self.llm = llm
        self.session_id = session_id

        get_df, create_df = sources_fn(sources)
        analyzer = analyzer_tool(sources, llm)
        df_tools = dataframe_tools(get_df, create_df)
        sk_tools, models, saved_models = scikit_tools(get_df, create_df, session_id)
        sc_tools = sources_tools(sources)

        self.agent = create_react_agent(
            model=chat_model,
            tools=[analyzer, *df_tools, *sk_tools, *sc_tools],
            prompt=SYSTEM_PROMPT.format(
                overview=format_sources_overview(sources),
                tool_intro=TOOL_INTRO,
            ),
            checkpointer=InMemorySaver(),
            pre_model_hook=pre_model_hook,
        )
        self.config = ensure_config({"recursion_limit": 200, "configurable": {"thread_id": threading.get_ident()}})
        self.trained_models = models
        self.saved_models = saved_models

    def get_messages(self) -> list[AnyMessage]:
        """获取当前 agent 的对话记录"""
        return self.agent.get_state(self.config).values["messages"]

    def create_title(self) -> str:
        return _create_title_chain(self.llm, self.get_messages()).invoke(...)

    async def create_title_async(self) -> str:
        return await _create_title_chain(self.llm, self.get_messages()).ainvoke(...)

    def summary(self) -> tuple[str, list[str]]:
        return _summary_chain(self.llm, self.get_messages()).invoke(...)

    async def summary_async(self) -> tuple[str, list[str]]:
        return await _summary_chain(self.llm, self.get_messages()).ainvoke(...)

    def load_state(self, state_file: Path) -> None:
        """从指定的状态文件加载 agent 状态。"""
        if not state_file.exists():
            return

        try:
            state = DataAnalyzerAgentState.model_validate_json(state_file.read_bytes())
        except ValueError:
            logger.warning("无法加载 agent 状态: 状态文件格式错误")
            return

        self.agent.update_state(self.config, state.values)
        self.saved_models.update(state.models)
        resume_tool_calls(self.sources, state.values["messages"])
        logger.opt(colors=True).info(f"已加载 agent 状态: <y>{len(state.values['messages'])}</>")

    def save_state(self, state_file: Path) -> None:
        """将当前 agent 状态保存到指定的状态文件。"""
        state = DataAnalyzerAgentState(
            values=cast("AgentValues", self.agent.get_state(self.config).values),
            models=self.saved_models,
        )
        state_file.write_bytes(state.model_dump_json().encode("utf-8"))
        logger.opt(colors=True).info(f"已保存 agent 状态: <y>{len(state.values['messages'])}</>")

    def stream(self, user_input: str) -> Iterator[StreamEvent]:
        """使用用户输入调用 agent，并以流式方式返回事件"""
        for event in self.agent.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config,
            stream_mode="messages",
        ):
            yield from process_stream_event(event)

    async def astream(self, user_input: str) -> AsyncIterator[StreamEvent]:
        """异步使用用户输入调用 agent，并以流式方式返回事件"""
        async for event in self.agent.astream(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config,
            stream_mode="messages",
        ):
            for evt in process_stream_event(event):
                yield evt
