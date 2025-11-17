import base64

from langchain_core.tools import tool

from app.core.agent.resume import resumable
from app.core.agent.schemas import AgentRuntimeContext
from app.core.chain import get_llm
from app.core.chain.nl_analysis import NL2DataAnalysis
from app.core.executor import CodeExecutor, format_result
from app.log import logger
from app.utils import escape_tag

from .registry import register_tool

TOOL_DESCRIPTION = """\
当你需要探索性数据分析或自定义可视化时使用该工具。

该工具会由另一个LLM生成代码，在隔离的Docker容器中执行并返回结果。

**重要限制**:
1. 在此工具中对数据的修改不会反映到其他工具可访问的DataFrame中
2. 创建的新列、转换数据或处理异常值仅在当前分析中有效
3. 如需保留数据修改，必须在分析后使用专用工具(如create_column_tool)重新实现

**适用场景**:
- 探索性数据分析和统计摘要
- 复杂的数据可视化(散点图、热图、分布图等)
- 临时数据转换和探索
- 特定问题的快速原型验证

**不适用场景**:
- 持久性数据转换(使用create_column_tool代替)
- 相关性分析(使用correlation_analysis_tool代替)
- 时滞分析(使用lag_analysis_tool代替)
- 异常检测(使用detect_outliers_tool代替)
- 模型训练(使用train_model_tool代替)

使用方式：提供要用于数据分析的数据集ID(dataset_id)和具体的分析需求描述(query)
**禁止直接编写分析代码**
"""


@tool(description=TOOL_DESCRIPTION, response_format="content_and_artifact")
@resumable
@register_tool("通用数据分析工具")
def analyze_data(
    dataset_id: str,
    query: str,
) -> tuple[str, dict[str, str]]:
    context = AgentRuntimeContext.get()
    logger.info(f"执行通用数据分析工具: dataset_id={dataset_id}")
    source = context.sources.get(dataset_id)

    with CodeExecutor(source) as executor:
        logger.opt(colors=True).info(f"<y>分析数据</> - 查询内容:\n{escape_tag(query)}")
        llm = get_llm(context.model_config.code_generation)
        result = NL2DataAnalysis(llm, executor=executor).invoke((source, query))

    # 处理图片结果
    artifact = {}
    if (fig := result["figure"]) is not None:
        # 创建包含图片的工具输出
        artifact = {
            "type": "image",
            "base64_data": base64.b64encode(fig).decode(),
            "caption": "分析图表输出",
        }

        return format_result(result), artifact
    return format_result(result), artifact


analyzer_tool = analyze_data
