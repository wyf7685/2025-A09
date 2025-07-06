import re

import pandas as pd
from langchain.prompts import PromptTemplate

from app.chain._base import BaseLLMRunnable
from app.log import logger
from app.utils import format_overview

from ..executor import CodeExecutor, ExecuteResult
from .llm import LLM


def code_parser(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if match := re.search(r"```(.*?)```", text, re.DOTALL):
        text = match.group(1).strip()
    return text.removeprefix("python").strip()


PROMPT_GENERATE_CODE = """\
你是一位数据分析专家，需要根据用户的自然语言分析需求生成Python代码。

示例数据:
{overview}

用户的分析需求:
{query}

根据用户需求生成 Python 代码，该代码需要对名为'df'的 DataFrame 进行操作。
代码应该高效、简洁，包含必要的注释。

重要规则：
1. 计算的最终结果必须赋值给名为'result'的变量
2. 如果结果是数据框架，请确保将最终的DataFrame赋值给'result'变量
3. 如果生成图表，仍然需要将关键数据赋值给'result'变量，并使用简短的输出描述图表的内容
4. 只需要返回可执行的Python代码，不需要解释
5. 部分数值类型可能为字符串，请确保在计算前将其转换为数值类型
6. 输出代码中 **禁止**包含示例数据

**禁止以下操作:**
- 禁止导入sklearn等机器学习库

允许使用的库: Python标准库、numpy、pandas、scipy、matplotlib、seaborn、statsmodels
代码执行环境: Python 3.12, Debian bookworm
"""


class NL2Code(
    BaseLLMRunnable[
        # overview, query
        tuple[str, str],
        # code
        str,
    ]
):
    def _run(self, input: tuple[str, str]) -> str:
        overview, query = input

        prompt = PromptTemplate(
            template=PROMPT_GENERATE_CODE,
            input_variables=["overview", "query"],
        )

        params = {"overview": overview, "query": query}
        return (prompt | self.llm | code_parser).invoke(params)


PROMPT_FIX_CODE = """\
你是一位经验丰富的数据分析编程专家，需要修复执行失败的Python代码。

【原始分析需求】
{query}

【数据预览】
{overview}

【原始生成的代码】
```python
{code}
```

【执行错误】
```
{error}
```

请修复上述代码，使其能够成功执行。代码应该对名为'df'的DataFrame进行操作，并将结果赋值给'result'变量。

修复指南:
1. 仔细分析错误消息，找出根本原因
2. 注意数据类型问题，CSV导入的数据可能需要类型转换(如将字符串转为数值)
3. 确保代码逻辑完整且符合原始分析需求
4. 保持代码高效简洁，包含必要的注释
5. 只返回修复后的完整Python代码，不要包含其他解释，**禁止**包含示例数据
6. 确保最终结果仍然存储在'result'变量中

**禁止以下操作:**
- 禁止导入sklearn等机器学习库

允许使用的库: Python标准库、numpy、pandas、scipy、matplotlib、seaborn、statsmodels
代码执行环境: Python 3.12, Debian bookworm
"""


class FixCode(
    BaseLLMRunnable[
        # query, overview, code, error
        tuple[str, str, str, str],
        # code
        str,
    ]
):
    def _run(self, input: tuple[str, str, str, str]) -> str:
        query, overview, code, error = input

        prompt = PromptTemplate(
            template=PROMPT_FIX_CODE,
            input_variables=["query", "overview", "code", "error"],
        )

        params = {
            "query": query,
            "overview": overview,
            "code": code,
            "error": error,
        }
        return (prompt | self.llm | code_parser).invoke(params)


class NL2DataAnalysis(
    BaseLLMRunnable[
        # overview | df, query
        tuple[str | pd.DataFrame, str],
        ExecuteResult,
    ]
):
    def __init__(
        self,
        llm: LLM,
        max_retry: int = 3,
        executor: CodeExecutor | None = None,
    ) -> None:
        super().__init__(llm)
        self.max_retry: int = max_retry
        self.executor = executor

    def execute(self, df: str | pd.DataFrame, query: str) -> ExecuteResult:
        if self.executor is None:
            if not isinstance(df, pd.DataFrame):
                raise ValueError("Data must be a pandas DataFrame")
            self.executor = CodeExecutor(df)

        overview = format_overview(df) if isinstance(df, pd.DataFrame) else df
        code = NL2Code(self.llm).invoke((overview, query))
        result = self.executor.execute(code)

        if result["success"]:
            return result

        fix = FixCode(self.llm)
        for _ in range(1, self.max_retry):
            error = result["error"] + "\n\n" + result["output"]
            code = fix.invoke((query, overview, code, error))
            result = self.executor.execute(code)
            if result["success"]:
                return result

        logger.warning(f"分析执行失败: \n{result['error']}")
        return result

    def _run(self, input: tuple[str | pd.DataFrame, str]) -> ExecuteResult:
        try:
            return self.execute(*input)
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"执行异常: {e}",
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
                "1. 数据格式可能与分析需求不匹配\n"
                "2. 分析查询可能需要澄清或重新表述\n"
                "3. 可能存在技术限制或数据质量问题"
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
