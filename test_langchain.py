import os
import re
from pathlib import Path
from typing import Literal

import dotenv
import matplotlib.pyplot as plt
import pandas as pd
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseLLM
from langchain_core.runnables import RunnableSerializable
from pydantic import BaseModel, Field

from code_executor import ExecuteResult, execute_code_in_docker, execute_code_with_exec

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
    def __init__(self) -> None:
        super().__init__(pydantic_object=CodeOutput)

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
    def __init__(self, llm: BaseLLM, execute_mode: Literal["exec", "docker"] = "exec"):
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
        sample_data: str,
        full_data: pd.DataFrame,
        query: str,
    ) -> ExecuteResult:
        """完整的分析流程"""
        code = self.generate_code(sample_data, query)
        print(f"生成的代码:\n\n{code}\n\n")
        return self.execute_code(code, full_data)


def main():
    from langchain_google_genai import GoogleGenerativeAI

    from dremio_client import DremioClient
    # from langchain_ollama import OllamaLLM
    # from langchain_openai import OpenAI

    with DremioClient().data_source_csv(Path("test.csv")) as source:
        df = source.read()

    model_name = os.environ["TEST_MODEL_NAME"]
    llm = GoogleGenerativeAI(model=model_name)
    # llm = OpenAI(model=model_name)
    # llm = OllamaLLM(model=model_name)
    analyzer = NL2DataAnalysis(
        llm,
        # execute_mode="docker",
    )

    queries = [
        "分析各学生的平均分",
        "分析学生的数学成绩统计量",
        "找出总成绩最高的学生",
    ]
    sample_data = df.head().to_string() + "\n\n" + df.dtypes.to_string()

    for query in queries:
        print(f"\n=== 分析需求: {query} ===")
        result = analyzer.analyze(sample_data, df, query)
        if result["success"]:
            if result["output"]:
                print("\n执行输出:")
                print(result["output"])
            if result["result"] is not None:
                print("\n计算结果:")
                print(result["result"])
            if result["figure"]:
                print("\n[图表已生成]")
                # result["figure"].show()
                plt.figure()
                plt.imshow(plt.imread(result["figure"]), aspect="auto")
                plt.axis("off")
                plt.show()
        else:
            print(f"\n执行失败: {result['error']}")


if __name__ == "__main__":
    main()
