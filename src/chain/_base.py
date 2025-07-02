from typing import override

from langchain_core.runnables import RunnableLambda

from .llm import LLM


class BaseRunnable[Input, Output](RunnableLambda[Input, Output]):
    @override
    def __init__(self) -> None:
        super().__init__(self._run)

    def _run(self, input: Input) -> Output:
        """执行具体的运行逻辑"""
        raise NotImplementedError("Subclasses must implement this method.")


class BaseLLMRunnable[Input, Output](BaseRunnable[Input, Output]):
    @override
    def __init__(self, llm: LLM) -> None:
        super().__init__()
        self.llm = llm
