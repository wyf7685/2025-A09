from io import BytesIO
from typing import override

import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable

from ._base import BaseLLMRunnable
from ..code_executor import ExecuteMode, ExecuteResult
from .nl_analysis import NL2DataAnalysis
from .parallel_runner import ParallelRunner

GENERAL_DATA_ANALYSIS_QUERIES_PROMPT = """\
你是一位资深的数据分析专家。根据给定的数据格式和示例数据，生成一系列有价值的分析问题。

数据格式和示例:
{overview}

请生成5条数据分析查询语句，这些查询应该：
1. 覆盖基础统计分析（如均值、分布、统计量等）
2. 包含趋势和对比分析
3. 探索数据之间的关系和相关性
4. 包含可视化需求
5. 关注异常值和特殊情况

生成的查询应该实用、明确，并且能从数据中获取有价值的见解。
每条查询单独一行，不要包含序号或其他格式标记。

{focus}

以下是查询示例格式：
分析各科目的平均成绩分布情况
找出成绩提升最显著的学生

请基于以上格式和要求，生成适合这份数据的分析查询。
"""

GENERAL_DATA_ANALYSIS_SUMMARY_PROMPT = """\
你是一位专业的数据分析师，需要基于多个分析结果编写一份完整的数据分析报告。

数据概览:
{overview}

分析结果列表:
{results}

请按照以下结构编写一份专业的数据分析报告：

1. 数据概述
- 简要说明数据的基本情况、维度和规模
- 数据质量评估

2. 主要发现
- 基于所有分析结果，总结3-5个最重要的发现
- 重点关注数据的分布特征、异常值和关键趋势

3. 详细分析
- 分析每个查询的结果
- 解释数据现象背后的可能原因
- 突出重要的统计指标和相关性

4. 结论与建议
- 总结关键结论
- 提出2-3条基于数据的具体建议
- 指出潜在的分析局限性

图表处理说明:
- 当你看到形如[图表已生成，ID=数字]的标记时，请在适当位置插入对应的Markdown图片引用
- 图片引用格式为: ![图表描述](./figure_数字.png)
- 为每个图表提供简短但有信息量的描述，说明其展示的主要内容
- 确保在正文中引用并解释每个图表的含义和重要发现

要求：
1. 使用专业但易懂的语言
2. 重点突出关键数据和重要发现
3. 保持客观、准确的分析态度
4. 确保结论有数据支持
5. 适当引用具体的数字和统计结果
6. 正确引用生成的图表

{focus}
"""


def format_overview(df: pd.DataFrame) -> str:
    return (
        f"数据规模: {df.shape[0]} 行 × {df.shape[1]} 列\n"
        f"列数据类型:\n{df.dtypes}\n"
        f"数据预览:\n{df.head().to_string()}"
    )


def format_focus(focus_areas: list[str] | None) -> tuple[str, str]:
    """格式化用户关注的分析方向"""
    if not focus_areas:
        return "", ""
    focus = "\n".join(f"- {focus}" for focus in focus_areas)
    return (
        f"用户特别关注以下分析方向，请确保生成的查询能够覆盖这些方向：\n{focus}",
        f"用户特别关注以下分析方向，请在报告中着重分析这些方面：\n{focus}",
    )


def format_analysis_result(query: str, result: ExecuteResult) -> str:
    """格式化单个分析结果为报告输入"""
    result_text = [f"查询: {query}", ""]

    if not result["success"]:
        result_text.append(f"分析失败: {result['error']}")
        print(f"\n\n分析 {query} 时出错: \n{result['error']}\n\n")
        return "\n".join(result_text)

    if result["output"]:
        result_text.append(f"<output>\n{result['output']}</output>")
    if result["result"] is not None:
        result_text.append(f"<result>\n{result['result']}</result>")
    if result["figure"]:
        result_text.append("[包含可视化图表]")

    return "\n".join(result_text)


class QueryGenerator(
    BaseLLMRunnable[
        # 输入数据: (overview, focus) / (overview)
        tuple[str, str | None] | str,
        # 输出: [query, ...]
        list[str],
    ]
):
    @override
    def _run(self, input: tuple[str, str | None] | str) -> list[str]:
        overview = input[0] if isinstance(input, tuple) else input
        focus = input[1] if isinstance(input, tuple) else None
        prompt = PromptTemplate(
            template=GENERAL_DATA_ANALYSIS_QUERIES_PROMPT,
            input_variables=["overview", "focus"],
        )
        params = {"overview": overview, "focus": focus or ""}
        text = (prompt | self.llm).invoke(params)
        return [q for q in map(str.strip, text.splitlines()) if q]


class GeneralSummary(
    BaseLLMRunnable[
        # 输入数据: (overview, [(query, result), ...], focus)
        tuple[str, list[tuple[str, ExecuteResult]], str],
        # 输出: (summary, figures)
        tuple[str, list[BytesIO]],
    ]
):
    @override
    def _run(
        self, input: tuple[str, list[tuple[str, ExecuteResult]], str]
    ) -> tuple[str, list[BytesIO]]:
        overview, results, focus = input
        figures: list[BytesIO] = []

        def format(query: str, result: ExecuteResult) -> str:
            text = format_analysis_result(query, result)
            if result["figure"] is not None:
                text += f"\n\n[图表已生成，ID={len(figures)}]"
                figures.append(result["figure"])
            return f"<analysis-item>{text}</analysis-item>"

        prompt = PromptTemplate(
            template=GENERAL_DATA_ANALYSIS_SUMMARY_PROMPT,
            input_variables=["overview", "results", "focus"],
        )
        formatted = "\n\n".join(format(query, result) for query, result in results)
        params = {"overview": overview, "results": formatted, "focus": focus}
        return (prompt | self.llm).invoke(params), figures


class GeneralDataAnalysis(
    BaseLLMRunnable[
        tuple[pd.DataFrame, list[str] | None] | pd.DataFrame,
        tuple[str, list[BytesIO]],
    ]
):
    def __init__(
        self,
        llm: Runnable[LanguageModelInput, str],
        max_workers: int | None = None,
        execute_mode: ExecuteMode = "exec",
    ) -> None:
        super().__init__(llm)
        self.max_workers = max_workers
        self.analyzer = NL2DataAnalysis(llm, execute_mode)

    def _run(
        self, input: tuple[pd.DataFrame, list[str] | None] | pd.DataFrame
    ) -> tuple[str, list[BytesIO]]:
        df = input[0] if isinstance(input, tuple) else input
        focus_areas = input[1] if isinstance(input, tuple) else None
        overview = format_overview(df)
        query_focus, summary_focus = format_focus(focus_areas)

        def worker(query: str) -> tuple[str, ExecuteResult]:
            return query, self.analyzer.invoke((df, query))

        chain = (
            (lambda _: (overview, query_focus))
            | QueryGenerator(self.llm)
            | ParallelRunner(worker, self.max_workers)
            | (lambda results: (overview, results, summary_focus))
            | GeneralSummary(self.llm)
        )
        return chain.invoke(...)
