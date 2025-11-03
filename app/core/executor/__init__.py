from app.core.config import settings

from .abstract import AbstractCodeExecutor as AbstractCodeExecutor
from .utils import ExecuteResult as ExecuteResult
from .utils import format_result as format_result

CodeExecutor: type[AbstractCodeExecutor]

if settings.DOCKER_RUNNER_IMAGE:
    from .container import ContaineredCodeExecutor as CodeExecutor
elif settings.EXECUTOR_DATA_DIR:
    from .compose import ComposedCodeExecutor as CodeExecutor
else:
    raise ValueError("无法确定代码执行器类型，请设置相应的环境变量：DOCKER_RUNNER_IMAGE 或 EXECUTOR_DATA_DIR")

__all__ = ["AbstractCodeExecutor", "CodeExecutor", "ExecuteResult", "format_result"]
