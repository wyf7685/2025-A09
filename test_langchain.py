import io
import os
import re
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import dotenv
from langchain_core.language_models import BaseLLM
from langchain_core.runnables import RunnableSerializable
import pandas as pd
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from matplotlib import pyplot as plt
from pydantic import BaseModel, Field

dotenv.load_dotenv()


class CodeOutput(BaseModel):
    python_code: str = Field(description="生成的Python代码，用于执行数据分析")


PROMPT_TEMPLATE = """\
你是一位数据分析专家，需要根据用户的自然语言分析需求生成Python代码。

示例数据:
{sample_data}

用户的分析需求:
{query}

根据用户需求生成Python代码，该代码需要对名为'df'的DataFrame进行操作。代码应该高效、简洁，包含必要的注释。
不要使用无法在Python标准库和pandas, numpy, matplotlib之外的库。

重要规则：
1. 计算的最终结果必须赋值给名为'result'的变量
2. 如果结果是数据框架，请确保将最终的DataFrame赋值给'result'变量
3. 如果生成图表，仍然需要将关键数据赋值给'result'变量
4. 只需要返回可执行的Python代码，不需要解释
5. 部分数值类型可能为字符串，请确保在计算前将其转换为数值类型
6. 输出代码中 **不应包含示例数据**

{format_instructions}
"""


class OutputParser(PydanticOutputParser[CodeOutput]):
    def parse(self, text: str) -> CodeOutput:
        cleaned_text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        try:
            return super().parse(cleaned_text.strip())
        except Exception:
            if code_match := re.search(r"```python(.*?)```", cleaned_text, re.DOTALL):
                code = code_match.group(1).strip()
                return CodeOutput(python_code=code)
            raise


class NL2DataAnalysis:
    def __init__(self, llm: BaseLLM):
        self.output_parser = PydanticOutputParser(pydantic_object=CodeOutput)
        self.code_generator: RunnableSerializable[dict, CodeOutput] = (
            self._create_prompt_template() | llm | OutputParser()
        )

    def _create_prompt_template(self):
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

    def execute_code(self, code: str, df: pd.DataFrame) -> dict[str, Any]:
        """
        在隔离环境中执行代码

        TODO: 使用 docker 实现
        """
        # 创建一个隔离的命名空间
        namespace = {
            "df": df.copy(),
            "pd": pd,
            "np": __import__("numpy"),
            "plt": __import__("matplotlib.pyplot"),
        }

        # 捕获标准输出
        output_buffer = io.StringIO()
        result = {
            "success": False,
            "output": "",
            "error": "",
            "result": None,
            "figure": None,
        }

        try:
            # 重定向标准输出
            with redirect_stdout(output_buffer):
                # 执行代码
                compiled_code = compile(code, "<string>", "exec")
                exec(compiled_code, namespace)

            # 检查是否有图表
            if (fig := plt.gcf()).get_axes():
                result["figure"] = fig

            # 捕获输出
            result["output"] = output_buffer.getvalue()

            # 如果代码定义了result变量，使用它作为结果
            if "result" in namespace:
                result["result"] = namespace["result"]

            result["success"] = True
        except Exception as e:
            result["error"] = f"执行错误: {str(e)}\n{traceback.format_exc()}"

        return result

    def analyze(
        self,
        sample_data: str,
        full_data: pd.DataFrame,
        query: str,
    ) -> dict[str, Any]:
        """完整的分析流程"""
        # 1. 生成代码
        code = self.generate_code(sample_data, query)

        # 2. 执行代码
        execution_result = self.execute_code(code, full_data)

        # 3. 返回结果
        return {
            "query": query,
            "generated_code": code,
            "execution_result": execution_result,
        }


def main():
    from dremio_client import DremioClient
    from langchain_google_genai import GoogleGenerativeAI
    # from langchain_ollama import OllamaLLM
    # from langchain_openai import OpenAI

    dremio = DremioClient()
    data_file = Path("test.csv")
    source_name = dremio.add_data_source_csv(data_file)

    df = dremio.read_source(source_name)
    sample_data = df.head().to_string() + "\n\n" + df.dtypes.to_string()

    queries = [
        "分析各学生的平均分",
        "分析学生的数学成绩统计量",
        "找出总成绩最高的学生",
    ]

    model_name = os.environ["TEST_MODEL_NAME"]
    llm = GoogleGenerativeAI(model=model_name)
    # llm = OpenAI(model=model_name, temperature=0)
    # llm = OllamaLLM(model=model_name)
    analyzer = NL2DataAnalysis(llm)
    for query in queries:
        print(f"\n=== 分析需求: {query} ===")
        result = analyzer.analyze(sample_data, df, query)

        print("\n生成的代码:")
        print(result["generated_code"])

        if result["execution_result"]["success"]:
            if result["execution_result"]["output"]:
                print("\n执行输出:")
                print(result["execution_result"]["output"])
            if result["execution_result"]["result"] is not None:
                print("\n计算结果:")
                print(result["execution_result"]["result"])
            if result["execution_result"]["figure"]:
                print("\n[图表已生成]")
                result["execution_result"]["figure"].show()
        else:
            print(f"\n执行失败: {result['execution_result']['error']}")


if __name__ == "__main__":
    main()
