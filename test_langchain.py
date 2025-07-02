import datetime
from io import BytesIO
import os
import re
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import dotenv
import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda

from code_executor import (
    ExecuteMode,
    ExecuteResult,
    execute_code,
)

dotenv.load_dotenv()


PROMPT_TEMPLATE = """\
你是一位数据分析专家，需要根据用户的自然语言分析需求生成Python代码。

示例数据:
{sample_data}

用户的分析需求:
{query}

根据用户需求生成 Python 代码，该代码需要对名为'df'的 DataFrame 进行操作。代码应该高效、简洁，包含必要的注释。
不要使用无法在 Python 标准库和 numpy, pandas, scipy, matplotlib, seaborn 之外的库。

重要规则：
1. 计算的最终结果必须赋值给名为'result'的变量
2. 如果结果是数据框架，请确保将最终的DataFrame赋值给'result'变量
3. 如果生成图表，仍然需要将关键数据赋值给'result'变量
4. 只需要返回可执行的Python代码，不需要解释
5. 部分数值类型可能为字符串，请确保在计算前将其转换为数值类型
6. 输出代码中 **不应包含示例数据**

"""


class NL2DataAnalysis:
    def __new__(
        cls,
        llm: Runnable[LanguageModelInput, str],
        execute_mode: ExecuteMode = "exec",
    ) -> Runnable[tuple[pd.DataFrame, str], ExecuteResult]:
        self = super().__new__(cls)
        self.__init__(llm, execute_mode)
        return RunnableLambda(self)

    def __init__(
        self,
        llm: Runnable[LanguageModelInput, str],
        execute_mode: ExecuteMode = "exec",
    ) -> None:
        self.llm = llm
        self.execute_mode: ExecuteMode = execute_mode

    def analyze(
        self,
        full_data: pd.DataFrame,
        query: str,
    ) -> ExecuteResult:
        """完整的分析流程"""

        def parser(text: str) -> str:
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
            if match := re.search(r"```(.*?)```", text, re.DOTALL):
                text = match.group(1).strip()
            return text.removeprefix("python").strip()

        prompt = PromptTemplate(
            template=PROMPT_TEMPLATE,
            input_variables=["sample_data", "query"],
        )

        chain = (prompt | self.llm | parser) | (
            lambda code: execute_code(self.execute_mode, code, full_data)
        )

        sample_data = str(full_data.dtypes) + "\n\n" + full_data.head().to_string()
        return chain.invoke({"sample_data": sample_data, "query": query})

    def __call__(self, input: tuple[pd.DataFrame, str]) -> ExecuteResult:
        try:
            return self.analyze(*input)
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"执行异常: {str(e)}",
                "result": None,
                "figure": None,
            }


GENERAL_DATA_ANALYSIS_QUERIES_PROMPT = """\
你是一位资深的数据分析专家。根据给定的数据格式和示例数据，生成一系列有价值的分析问题。

数据格式和示例:
{sample_data}

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


class ParallelRunner[Input, Output]:
    def __new__(
        cls,
        func: Runnable[Input, Output] | Callable[[Input], Output],
        max_workers: int | None = None,
    ) -> Runnable[Sequence[Input], Sequence[Output]]:
        self = super().__new__(cls)
        self.__init__(func, max_workers)
        return RunnableLambda(self)

    def __init__(
        self,
        func: Runnable[Input, Output] | Callable[[Input], Output],
        max_workers: int | None = None,
    ) -> None:
        self.func: Callable[[Input], Output] = (
            func.invoke if isinstance(func, Runnable) else func
        )
        self.max_workers = max_workers

    def __call__(self, inputs: Sequence[Input]) -> Sequence[Output]:
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_input = {executor.submit(self.func, inp): inp for inp in inputs}
            return [future.result() for future in as_completed(future_to_input)]


class GeneralDataAnalysis:
    def __new__(
        cls,
        llm: Runnable[LanguageModelInput, str],
        max_workers: int | None = None,
        execute_mode: ExecuteMode = "exec",
    ) -> Runnable[
        tuple[pd.DataFrame, list[str] | None] | pd.DataFrame,
        tuple[str, list[BytesIO]],
    ]:
        self = super().__new__(cls)
        self.__init__(llm, max_workers, execute_mode)
        return RunnableLambda(self)

    def __init__(
        self,
        llm: Runnable[LanguageModelInput, str],
        max_workers: int | None = None,
        execute_mode: ExecuteMode = "exec",
    ) -> None:
        self.llm = llm
        self.max_workers = max_workers
        self.analyzer = NL2DataAnalysis(llm, execute_mode)

    def format_preview(self, df: pd.DataFrame) -> str:
        return (
            f"数据规模: {df.shape[0]} 行 × {df.shape[1]} 列\n"
            f"列数据类型:\n{df.dtypes}\n"
            f"数据预览:\n{df.head().to_string()}"
        )

    def format_focus(self, focus_areas: list[str] | None) -> tuple[str, str]:
        """格式化用户关注的分析方向"""
        if not focus_areas:
            return "", ""
        focus = "\n".join(f"- {focus}" for focus in focus_areas)
        return (
            f"用户特别关注以下分析方向，请确保生成的查询能够覆盖这些方向：\n{focus}",
            f"用户特别关注以下分析方向，请在报告中着重分析这些方面：\n{focus}",
        )

    def analyze(
        self,
        df: pd.DataFrame,
        focus_areas: list[str] | None = None,
    ) -> tuple[str, list[BytesIO]]:
        """执行完整的数据分析流程"""
        preview = self.format_preview(df)
        query_focus, summary_focus = self.format_focus(focus_areas)
        result_figures: list[BytesIO] = []

        prompt_queries = PromptTemplate(
            template=GENERAL_DATA_ANALYSIS_QUERIES_PROMPT,
            input_variables=["sample_data", "focus"],
        )
        prompt_summary = PromptTemplate(
            template=GENERAL_DATA_ANALYSIS_SUMMARY_PROMPT,
            input_variables=["overview", "results", "focus"],
        )

        def analyze(query: str) -> str:
            result = self.analyzer.invoke((df, query))
            formatted = format_analysis_result(query, result)
            if result["figure"] is not None:
                formatted += f"\n\n[图表已生成，ID={len(result_figures)}]"
                result_figures.append(result["figure"])
            return f"<analysis-item>{formatted}</analysis-item>"

        chain = (
            (lambda _: {"sample_data": preview, "focus": query_focus})
            | (prompt_queries | self.llm)
            | (lambda text: filter(None, map(str.strip, str(text).splitlines())))
            | ParallelRunner[str, str](analyze, self.max_workers)
            | (
                lambda results: {
                    "overview": preview,
                    "results": "\n\n".join(results),
                    "focus": summary_focus,
                }
            )
            | (prompt_summary | self.llm)
        )

        return chain.invoke(...), result_figures

    def __call__(
        self, input: tuple[pd.DataFrame, list[str] | None] | pd.DataFrame
    ) -> tuple[str, list[BytesIO]]:
        return self.analyze(*input) if isinstance(input, tuple) else self.analyze(input)


def get_llm() -> Runnable[LanguageModelInput, str]:
    """获取配置的LLM实例"""
    model_name = os.environ.get("TEST_MODEL_NAME")
    assert model_name, "TEST_MODEL_NAME 环境变量未设置"

    if "GOOGLE_API_KEY" in os.environ:
        from langchain_google_genai import GoogleGenerativeAI

        print("使用 Google Generative AI 模型")
        return GoogleGenerativeAI(model=model_name)

    if "OPENAI_API_KEY" in os.environ:
        from langchain_openai import ChatOpenAI

        print("使用 OpenAI 模型")

        def convert(msg: BaseMessage) -> str:
            if isinstance(msg.content, str):
                return msg.content
            if isinstance(msg.content, list):
                return "\n".join(str(m) for m in msg.content)
            raise ValueError(f"Unsupported message content type: {type(msg.content)}")

        return ChatOpenAI(model=model_name) | convert

    from langchain_ollama import OllamaLLM

    print("未检测到模型配置，尝试使用本地部署 Ollama 模型")
    return OllamaLLM(model=model_name)


def test_general_analyze():
    from dremio_client import DremioClient

    with DremioClient().data_source_csv(Path("test.csv")) as source:
        df = source.read(fetch_all=True)

    print("数据预览:")
    print(df.head().to_string())
    print("\n数据规模:", df.shape)
    print("\n请输入您关注的分析方向（多个方向用逗号分隔，直接回车则不设置侧重点）：")
    print("例如：趋势分析,异常值检测,相关性分析")
    user_input = input("> ").strip()
    focus_areas = [i.strip() for i in user_input.split(",")] if user_input else None

    analyzer = GeneralDataAnalysis(get_llm().with_retry(), execute_mode="docker")
    report, figures = analyzer.invoke((df, focus_areas))
    print("\n\n分析报告:")
    print(report)

    output_dir = Path("output") / datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    for i, figure_data in enumerate(figures):
        with (output_dir / f"figure_{i}.png").open("wb") as f:
            f.write(figure_data.getvalue())
    print(f"\n\n报告和图表已保存到: {output_dir}")

if __name__ == "__main__":
    test_general_analyze()
