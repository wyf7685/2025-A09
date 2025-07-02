import re

import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

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


class NL2DataAnalysis(RunnableLambda[tuple[pd.DataFrame, str], ExecuteResult]):
    def __init__(
        self,
        llm: LLM,
        execute_mode: ExecuteMode = "exec",
    ) -> None:
        super().__init__(self._run)
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


def __demo__():
    """演示如何使用NL2DataAnalysis类"""
    import pandas as pd

    data = {
        "日期": pd.date_range(start="2023-01-01", periods=5, freq="D"),
        "销售额": [100, 200, 150, 300, 250],
        "成本": [80, 150, 120, 200, 180],
    }
    df = pd.DataFrame(data)
    analyzer = NL2DataAnalysis(llm=RunnableLambda(lambda x: "模拟LLM响应"))
    result: ExecuteResult = analyzer.invoke((df, "计算每月的利润和趋势"))
    print(result)
