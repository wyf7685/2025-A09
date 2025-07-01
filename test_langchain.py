import os
import re
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import dotenv
import matplotlib.pyplot as plt
import pandas as pd
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from code_executor import ExecuteResult, execute_code_in_docker, execute_code_with_exec

dotenv.load_dotenv()


class CodeOutput(BaseModel):
    python_code: str = Field(description="生成的Python代码，用于执行数据分析")


class OutputParser(PydanticOutputParser[CodeOutput]):
    def __init__(self) -> None:
        super().__init__(pydantic_object=CodeOutput)

    def parse(self, text: str) -> CodeOutput:
        cleaned_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        try:
            return super().parse(cleaned_text.strip())
        except Exception:
            if code_match := re.search(
                r"```[a-zA-Z0-9]*?\n?(.*?)```", cleaned_text, re.DOTALL
            ):
                code = code_match.group(1).strip()
                return CodeOutput(python_code=code)
            raise


PROMPT_TEMPLATE = """\
你是一位数据分析专家，需要根据用户的自然语言分析需求生成Python代码。

示例数据:
{sample_data}

用户的分析需求:
{query}

根据用户需求生成 Python 代码，该代码需要对名为'df'的 DataFrame 进行操作。代码应该高效、简洁，包含必要的注释。
不要使用无法在 Python 标准库和 pandas, numpy, matplotlib, seaborn 之外的库。

重要规则：
1. 计算的最终结果必须赋值给名为'result'的变量
2. 如果结果是数据框架，请确保将最终的DataFrame赋值给'result'变量
3. 如果生成图表，仍然需要将关键数据赋值给'result'变量
4. 只需要返回可执行的Python代码，不需要解释
5. 部分数值类型可能为字符串，请确保在计算前将其转换为数值类型
6. 输出代码中 **不应包含示例数据**

{format_instructions}
"""


class NL2DataAnalysis:
    def __new__(
        cls,
        llm: Runnable[LanguageModelInput, str],
        execute_mode: Literal["exec", "docker"] = "exec",
    ) -> Runnable[tuple[pd.DataFrame, str], ExecuteResult]:
        self = super().__new__(cls)
        self.__init__(llm, execute_mode)
        return RunnableLambda(self)

    def __init__(
        self,
        llm: Runnable[LanguageModelInput, str],
        execute_mode: Literal["exec", "docker"] = "exec",
    ):
        self.execute_mode = execute_mode
        self.output_parser = OutputParser()
        self.code_generator: RunnableSerializable[dict, CodeOutput] = (
            self._create_prompt_template() | llm | self.output_parser
        )

    def _create_prompt_template(self) -> PromptTemplate:
        return PromptTemplate(
            template=PROMPT_TEMPLATE,
            input_variables=["sample_data", "query"],
            partial_variables={
                "format_instructions": self.output_parser.get_format_instructions()
            },
        )

    def generate_code(self, sample_data: str, query: str) -> str:
        """根据数据描述、示例数据和查询生成Python代码"""
        return self.code_generator.invoke(
            {"sample_data": sample_data, "query": query}
        ).python_code

    def execute_code(self, code: str, df: pd.DataFrame) -> ExecuteResult:
        """在Docker容器中执行生成的代码"""
        return (
            execute_code_with_exec
            if self.execute_mode == "exec"
            else execute_code_in_docker
        )(code, df)

    def analyze(
        self,
        full_data: pd.DataFrame,
        query: str,
    ) -> ExecuteResult:
        """完整的分析流程"""
        sample_data = str(full_data.dtypes) + "\n\n" + full_data.head().to_string()
        code = self.generate_code(sample_data, query)
        # print(f"生成的代码:\n\n{code}\n\n")
        return self.execute_code(code, full_data)

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

以下是查询示例格式：
分析各科目的平均成绩分布情况
找出成绩提升最显著的学生

请基于以上格式和要求，生成适合这份数据的分析查询。
"""

GENERAL_DATA_ANALYSIS_SUMMARY_PROMPT = """\
你是一位专业的数据分析师，需要基于多个分析结果编写一份完整的数据分析报告。

数据概览:
{data_overview}

分析结果列表:
{analysis_results}

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

要求：
1. 使用专业但易懂的语言
2. 重点突出关键数据和重要发现
3. 保持客观、准确的分析态度
4. 确保结论有数据支持
5. 适当引用具体的数字和统计结果
"""


@dataclass
class AnalysisItem:
    """单个分析项的结果"""

    query: str
    result: ExecuteResult


def format_analysis_results(results: Sequence[AnalysisItem]) -> str:
    """格式化分析结果为报告输入"""
    formatted_results: list[list[str]] = []

    for item in results:
        result_text = ["---", f"查询: {item.query}", ""]
        formatted_results.append(result_text)

        if not item.result["success"]:
            result_text.append(f"分析失败: {item.result['error']}")
            continue

        if item.result["output"]:
            result_text.append(f"<output>\n{item.result['output']}</output>")
        if item.result["result"] is not None:
            result_text.append(f"<result>\n{item.result['result']}</result>")
        if item.result["figure"]:
            result_text.append("[包含可视化图表]")

    return "\n\n".join(
        f"<analysis-item>\n{'\n'.join(lines).strip()}\n</analysis-item>"
        for lines in formatted_results
    )


class ParallelRunner[Input, Output]:
    def __init__(
        self,
        func: Callable[[Input], Output],
        max_workers: int | None = None,
    ) -> None:
        self.func = func
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
        execute_mode: Literal["exec", "docker"] = "exec",
    ) -> Runnable[pd.DataFrame, str]:
        self = super().__new__(cls)
        self.__init__(llm, max_workers, execute_mode)
        return RunnableLambda(self.analyze)

    def __init__(
        self,
        llm: Runnable[LanguageModelInput, str],
        max_workers: int | None = None,
        execute_mode: Literal["exec", "docker"] = "exec",
    ) -> None:
        self.llm = llm
        self.max_workers = max_workers
        self.execute_mode: Literal["exec", "docker"] = execute_mode

    def analyze(self, df: pd.DataFrame) -> str:
        """执行完整的数据分析流程"""
        preview = (
            f"数据规模: {df.shape[0]} 行 × {df.shape[1]} 列\n"
            f"列数据类型:\n{df.dtypes}\n"
            f"数据预览:\n{df.head().to_string()}"
        )

        analyzer = NL2DataAnalysis(self.llm, self.execute_mode)
        analysis_chain = (
            PromptTemplate(
                template=GENERAL_DATA_ANALYSIS_QUERIES_PROMPT,
                input_variables=["sample_data"],
            )
            | self.llm
            | (lambda text: [q.strip() for q in str(text).split("\n") if q.strip()])
            | ParallelRunner[str, AnalysisItem](
                (lambda query: AnalysisItem(query, analyzer.invoke((df, query)))),
                max_workers=self.max_workers,
            )
            | format_analysis_results
            | (lambda results: {"data_overview": preview, "analysis_results": results})
            | PromptTemplate(
                template=GENERAL_DATA_ANALYSIS_SUMMARY_PROMPT,
                input_variables=["data_overview", "analysis_results"],
            )
            | self.llm
        )

        return analysis_chain.invoke({"sample_data": preview})


def get_llm() -> Runnable[LanguageModelInput, str]:
    """获取配置的LLM实例"""
    model_name = os.environ.get("TEST_MODEL_NAME")
    assert model_name, "TEST_MODEL_NAME 环境变量未设置"

    if "GOOGLE_API_KEY" in os.environ:
        from langchain_google_genai import GoogleGenerativeAI

        print("使用 Google Generative AI 模型")
        return GoogleGenerativeAI(model=model_name)
    elif "OPENAI_API_KEY" in os.environ:
        from langchain_openai import ChatOpenAI

        print("使用 OpenAI 模型")

        def convert(msg: BaseMessage) -> str:
            if isinstance(msg.content, str):
                return msg.content
            if isinstance(msg.content, list):
                return "\n".join(str(m) for m in msg.content)
            raise ValueError(f"Unsupported message content type: {type(msg.content)}")

        return ChatOpenAI(model=model_name) | convert
    else:
        from langchain_ollama import OllamaLLM

        print("未检测到模型配置，尝试使用本地部署 Ollama 模型")
        return OllamaLLM(model=model_name)


def main():
    from dremio_client import DremioClient

    with DremioClient().data_source_csv(Path("test.csv")) as source:
        df = source.read()

    analyzer = NL2DataAnalysis(get_llm())

    queries = [
        "分析各学生的平均分",
        "分析学生的数学成绩统计量",
        "找出总成绩最高的学生",
    ]

    for query in queries:
        print(f"\n=== 分析需求: {query} ===")
        result = analyzer.invoke((df, query))
        if result["success"]:
            if result["output"]:
                print("\n执行输出:")
                print(result["output"])
            if result["result"] is not None:
                print("\n计算结果:")
                print(result["result"])
            if result["figure"]:
                print("\n[图表已生成]")
                plt.figure()
                plt.imshow(plt.imread(result["figure"]), aspect="auto")
                plt.axis("off")
                plt.show()
        else:
            print(f"\n执行失败: {result['error']}")


def test_general_analyze():
    from dremio_client import DremioClient

    with DremioClient().data_source_csv(Path("test.csv")) as source:
        df = source.read()

    analyzer = GeneralDataAnalysis(get_llm().with_retry(), execute_mode="docker")
    result = analyzer.invoke(df)
    print("\n\n分析报告:")
    print(result)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    Path("output/report.md").write_text(result, encoding="utf-8")


if __name__ == "__main__":
    # main()
    test_general_analyze()
