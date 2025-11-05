import ast
from abc import ABC, abstractmethod
from typing import Self

import anyio.to_thread

from app.core.datasource import DataSource

from .utils import ExecuteResult


class AbstractCodeExecutor(ABC):
    @abstractmethod
    def __init__(self, data_source: DataSource) -> None: ...

    def __enter__(self) -> Self:
        """使用上下文管理器启动容器"""
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """退出上下文管理器时关闭容器"""
        self.stop()

    @abstractmethod
    def start(self) -> None:
        """启动Docker容器"""

    @abstractmethod
    def stop(self) -> None:
        """停止并移除Docker容器"""

    async def astop(self) -> None:
        await anyio.to_thread.run_sync(self.stop)

    @abstractmethod
    def execute(self, code: str) -> ExecuteResult: ...

    def _check_code(self, code: str) -> ExecuteResult | None:
        # 验证代码语法
        try:
            ast.parse(code)
        except SyntaxError as err:
            return {
                "success": False,
                "output": "",
                "error": f"代码语法错误 (行 {err.lineno} 列 {err.offset}): {err.msg}",
                "result": None,
                "figure": None,
            }
