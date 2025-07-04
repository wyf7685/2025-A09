import base64

import pandas as pd
from langchain_core.tools import Tool

from app.chain.llm import LLM
from app.chain.nl_analysis import NL2DataAnalysis
from app.executor import CodeExecutor, ExecuteResult, format_result
from app.log import logger
from app.utils import format_overview


def tool_analyzer(df: pd.DataFrame, llm: LLM) -> tuple[Tool, list[ExecuteResult]]:
    """
    创建一个数据分析工具，使用提供的DataFrame和语言模型。

    Args:
        df (pd.DataFrame): 要用于数据分析的DataFrame。
        llm (LLM): 用于生成分析代码的语言模型。

    Returns:
        Tool: 用于数据分析的LangChain工具。
    """
    analyzer = NL2DataAnalysis(llm, executor=CodeExecutor(df))
    overview = format_overview(df)
    results: list[ExecuteResult] = []

    def analyze(query: str) -> tuple[str, dict[str, str]]:
        logger.info(f"Analyzing data with query: {query}")
        result = analyzer.invoke((overview, query))
        results.append(result)

        # 处理图片结果
        artifact = {}
        if (fig := result["figure"]) is not None:
            # 创建包含图片的工具输出
            artifact = {
                "type": "image",
                "base64_data": base64.b64encode(fig.getvalue()).decode(),
                "caption": "分析图表输出",
            }

        return format_result(result), artifact

    tool = Tool(
        name="analyze_data",
        description="当你需要对数据进行分析时使用该工具。"
        "提供你的分析需求，工具将根据请求内容执行Python代码并返回结果。"
        "**无需自己编写代码**，只需具体描述你需要执行的分析。",
        func=analyze,
    )
    tool.response_format = "content_and_artifact"
    return tool, results
