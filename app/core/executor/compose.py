import time
import uuid
from weakref import finalize

from app.core.config import settings
from app.core.datasource import DataSource
from app.log import logger

from .abstract import AbstractCodeExecutor
from .utils import ExecuteResult, parse_result


class ComposedCodeExecutor(AbstractCodeExecutor):
    def __init__(self, data_source: DataSource) -> None:
        """
        初始化代码执行器

        Args:
            data_source: 数据源对象，提供数据访问接口
            image: Docker镜像名称
            memory_limit: 内存限制
            cpu_shares: CPU使用限制
        """
        if not settings.EXECUTOR_DATA_DIR:
            raise ValueError("请设置 EXECUTOR_DATA_DIR 环境变量以使用 ComposedCodeExecutor")

        self._data_dir = settings.EXECUTOR_DATA_DIR
        self.data_source = data_source

        finalize(self, self.stop)

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def execute(self, code: str) -> ExecuteResult:
        """
        在Docker容器中执行代码

        Args:
            code: 要执行的Python代码

        Returns:
            ExecuteResult: 执行结果
        """
        if result := self._check_code(code):
            return result

        logger.info(f"正在执行代码:\n{code}")
        data_dir = self._data_dir / uuid.uuid4().hex
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "input.py").write_text(code, encoding="utf-8")
        self.data_source.get_full().to_csv(data_dir / "data.csv", index=False)
        output_file = data_dir / "output.json"
        while not output_file.exists():
            time.sleep(0.5)

        output_data = output_file.read_bytes()
        output_file.unlink()
        return parse_result(output_data)
