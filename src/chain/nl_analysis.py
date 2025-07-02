import re

import pandas as pd
from langchain.prompts import PromptTemplate

from src.chain._base import BaseLLMRunnable

from ..code_executor import ExecuteMode, ExecuteResult, execute_code
from .llm import LLM

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


class NL2DataAnalysis(BaseLLMRunnable[tuple[pd.DataFrame, str], ExecuteResult]):
    def __init__(
        self,
        llm: LLM,
        execute_mode: ExecuteMode = "exec",
    ) -> None:
        super().__init__(llm)
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

    def _run(self, input: tuple[pd.DataFrame, str]) -> ExecuteResult:
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


PROMPT_SUMMARY = """\
你是一位数据分析解释专家，需要根据分析结果为用户提供清晰易懂的总结。

原始分析需求:
{query}

执行结果:
{output}

分析结果:
{result}

请提供一个专业且易懂的分析总结，包含以下内容:
1. 简述分析的目标和方法
2. 详细解释关键发现和结果的含义
3. 提供结果的业务解读和洞察
4. 如有图表，解释图表展示的主要信息
5. 指出潜在的局限性或需要进一步分析的方向

总结应保持专业性的同时，确保非技术人员也能理解。使用清晰的语言和结构化的格式。

如果分析执行失败，请说明可能的原因并提供改进建议。
"""


class NLAnalysisSummary(BaseLLMRunnable[tuple[str, ExecuteResult], str]):
    """对NL2DataAnalysis的执行结果进行专业总结的可运行组件"""

    def _run(self, input: tuple[str, ExecuteResult]) -> str:
        query, result = input

        if not result["success"]:
            return (
                f"分析执行失败。错误信息: \n{result['error']}\n\n可能的原因：\n"
                + "1. 数据格式可能与分析需求不匹配\n"
                + "2. 分析查询可能需要澄清或重新表述\n"
                + "3. 可能存在技术限制或数据质量问题"
            )

        result_text = ""
        data = result["result"]
        if data is not None:
            if isinstance(data, pd.DataFrame):
                result_text = f"DataFrame结果 (形状: {data.shape}):\n{data.to_string()}"
            elif isinstance(data, pd.Series):
                result_text = f"Series结果 (长度: {len(data)}):\n{data.to_string()}"
            else:
                result_text = str(data)

        if result["figure"] is not None:
            result_text += "\n\n[分析生成了可视化图表]"

        prompt = PromptTemplate(
            template=PROMPT_SUMMARY,
            input_variables=["query", "output", "result"],
        )

        params = {
            "query": query,
            "output": result["output"],
            "result": result_text,
        }
        return (prompt | self.llm).invoke(params)


def __demo__():
    """演示如何使用NL2DataAnalysis类"""
    import pandas as pd

    from .llm import get_llm

    data = {
        "日期": pd.date_range(start="2023-01-01", periods=5, freq="D"),
        "销售额": [100, 200, 150, 300, 250],
        "成本": [80, 150, 120, 200, 180],
    }
    df = pd.DataFrame(data)
    query = "计算每月的利润和趋势"
    llm = get_llm()

    result: ExecuteResult = NL2DataAnalysis(llm).invoke((df, query))
    print(result)

    summary = NLAnalysisSummary(llm).invoke((query, result))
    print("分析总结:")
    print(summary)
