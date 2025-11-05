import re

import pandas as pd
from langchain.prompts import PromptTemplate

from app.core.datasource import DataSource
from app.core.executor import AbstractCodeExecutor, CodeExecutor, ExecuteResult
from app.log import logger

from ._base import BaseLLMRunnable
from .llm import LLM

_filter_patterns = [
    re.compile(r"plt\.rcParams\[.font\.family.\]\s*=\s*\[.*?\]"),  # plt.rcParams["font.family"] = [...]
    re.compile(r"plt\.rcParams\[.axes\.unicode_minus.\]\s*=\s*.*"),  # plt.rcParams["axes.unicode_minus"] = ...
    re.compile(r"plt\.rcParams\[.font\.sans-serif.\]\s*=\s*\[.*?\]"),  # plt.rcParams["font.sans-serif"] = [...]
    re.compile(r"plt\.rcParams\[.font\.serif.\]\s*=\s*\[.*?\]"),  # plt.rcParams["font.serif"] = [...]
]


def code_filter(text: str) -> str:
    # 过滤 plt.rcParams[] 设置中文字体的代码
    for pattern in _filter_patterns:
        text = pattern.sub("", text)
    return text


def code_parser(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if match := re.search(r"```(.*?)```", text, re.DOTALL):
        text = match.group(1).strip()
    return code_filter(text.removeprefix("python").strip())


PROMPT_GENERATE_CODE = """\
你是一位数据分析专家，需要根据用户的自然语言分析需求生成Python代码。

示例数据:
<overview>
{overview}
</overview>

用户的分析需求:
<query>
{query}
</query>

请生成高质量的Python代码，对名为'df'的DataFrame进行操作，满足以下要求：

## 代码格式要求
1. 代码应简洁高效，包含必要的注释解释关键步骤
2. 最终结果必须赋值给名为'result'变量
3. 仅输出可执行的Python代码，不要包含解释文本或Markdown标记

## 数据处理要求
1. 检查并处理数据类型问题，尤其是将字符串转换为适当的数值类型
2. 处理可能存在的缺失值和异常值
3. 适当展示处理前后的数据对比，帮助理解变化

## 可视化要求
1. 使用合适的图表类型展示数据特征和关系
2. 设置合理的图表尺寸、标题和标签（使用中文标识以增强可读性）
3. 使用plt.tight_layout()和合适的DPI确保图表清晰
4. 通过设置图表的字体大小和样式提高可读性
5. 如果生成图表，将关键统计数据作为字典或DataFrame赋值给'result'变量
6. 图表中的中文字体设置请使用系统预置字体：'WenQuanYi Micro Hei'、'WenQuanYi Zen Hei'、'AR PL UKai CN'或'AR PL UMing CN'
7. 不要使用'SimHei'、'SimSun'等Windows专有字体

## 结果输出要求
1. DataFrame结果：直接将DataFrame赋值给'result'
2. 统计分析结果：使用字典或Series格式赋值给'result'
3. 图表分析：除了显示图表外，将关键统计指标赋值给'result'
4. 输出少量关键信息，说明分析完成和结果含义

## 禁止操作
1. 禁止导入sklearn等机器学习库和其他非标准分析库
2. 禁止在代码中包含任何示例数据
3. 禁止尝试写入或读取外部文件
4. 禁止覆盖或重新定义'df'变量
5. 禁止使用不在Docker环境中的字体，如'SimHei'、'SimSun'、'Microsoft YaHei'等

## 重要警告
1. 'df'变量已预先定义，直接使用即可，不需要检查其是否存在
2. 不要在代码开头创建新的DataFrame或覆盖'df'变量
3. 不要添加类似'if "df" not in locals():'或'if df is None:'的检查
4. 不要使用示例数据替代已经存在的'df'变量
5. 所有操作都应基于已存在的'df' DataFrame进行，而不是创建新数据
6. 绘图字体应使用系统提供的字体，如'WenQuanYi Micro Hei'，而不是'SimHei'

Docker环境已经配置了中文字体支持，可以直接在图表中使用中文标题、标签和注释。
允许使用的库: Python标准库、numpy、pandas、scipy、matplotlib、statsmodels
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
<code>
{code}
</code>

【执行错误】
<error>
{error}
</error>

请修复上述代码，使其能够成功执行。代码应该对名为'df'的DataFrame进行操作，并将结果赋值给'result'变量。

## 修复指南
1. 仔细分析错误消息，找出根本原因
2. 注意数据类型问题，将字符串转为适当的数值类型
3. 检查列名是否正确，包括大小写和空格
4. 确保代码逻辑完整且符合原始分析需求
5. 处理可能的缺失值和异常值
6. 只返回修复后的完整Python代码，不要包含其他解释

## 常见错误修复
1. 列名不存在：检查列名大小写和拼写，使用df.columns查看所有可用列
2. 类型转换问题：添加适当的类型转换代码，如pd.to_numeric()
3. 缺失值问题：使用df.fillna()或过滤缺失值
4. 图表显示问题：确保正确设置字体和图表参数
5. 字体错误：不要使用'SimHei'等Windows专有字体，应该使用'WenQuanYi Micro Hei'等Docker环境中可用的字体

## 重要规则
1. 'df'变量已预先定义，直接使用即可，不要重新定义或检查其是否存在
2. 不要在代码开头创建新的DataFrame或覆盖'df'变量
3. 不要添加类似'if "df" not in locals():'或'if df is None:'的检查
4. 不要使用示例数据替代已存在的'df'变量
5. 确保最终结果存储在'result'变量中
6. 禁止导入sklearn等机器学习库和其他非标准分析库
7. 禁止尝试写入或读取外部文件
8. 绘图字体必须使用Docker环境中可用的字体，如'WenQuanYi Micro Hei'，不要使用'SimHei'、'SimSun'或'Microsoft YaHei'

Docker环境已经配置了中文字体支持，可以直接在图表中使用中文标题、标签和注释。
允许使用的库: Python标准库、numpy、pandas、scipy、matplotlib、statsmodels
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
        tuple[DataSource, str],
        ExecuteResult,
    ]
):
    def __init__(
        self,
        llm: LLM,
        max_retry: int = 3,
        executor: AbstractCodeExecutor | None = None,
    ) -> None:
        super().__init__(llm)
        self.max_retry: int = max_retry
        self.executor = executor

    def execute(self, source: DataSource, query: str) -> ExecuteResult:
        if self.executor is None:
            self.executor = CodeExecutor(source)

        overview = source.format_overview()

        code = NL2Code(self.llm).invoke((overview, query))

        result = self.executor.execute(code)
        logger.info(f"初始分析执行结果: success={result['success']}")

        if result["success"]:
            return result

        fix = FixCode(self.llm)
        for attempt in range(1, self.max_retry + 1):
            error = result["error"] + "\n\n" + result["output"]
            logger.info(f"尝试修复分析代码并重新执行: {attempt}/{self.max_retry}\n{error}")
            code = fix.invoke((query, overview, code, error))
            result = self.executor.execute(code)
            logger.info(f"修复后分析执行结果: success={result['success']}")
            if result["success"]:
                return result

        logger.warning(f"分析执行失败: \n{result['error']}")
        return result

    def _run(self, input: tuple[DataSource, str]) -> ExecuteResult:
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
