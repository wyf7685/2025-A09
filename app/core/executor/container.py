import shutil
import tempfile
import time
from pathlib import Path
from weakref import finalize

import docker
import docker.errors

from app.core.config import settings
from app.core.datasource import DataSource
from app.log import logger
from app.utils import escape_tag

from .abstract import AbstractCodeExecutor
from .utils import ExecuteResult, parse_result


class ContaineredCodeExecutor(AbstractCodeExecutor):
    """
    代码执行器类，生命周期内控制一个Docker容器
    """

    def __init__(
        self,
        data_source: DataSource,
        image: str | None = None,
        memory_limit: str = "512m",
        cpu_shares: int = 2,
    ) -> None:
        """
        初始化代码执行器

        Args:
            data_source: 数据源对象，提供数据访问接口
            image: Docker镜像名称
            memory_limit: 内存限制
            cpu_shares: CPU使用限制
        """
        image = image or settings.DOCKER_RUNNER_IMAGE
        if not image:
            raise ValueError("Docker镜像名称未指定，请设置DOCKER_RUNNER_IMAGE环境变量")

        self.data_source = data_source
        self.image = image
        self.memory_limit = memory_limit
        self.cpu_shares = cpu_shares
        self.container = None
        self.temp_dir = None

        finalize(self, self.stop)

    def start(self) -> None:
        """启动Docker容器"""
        if self.container:
            return

        self.temp_dir = Path(tempfile.mkdtemp())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.data_source.get_full().to_csv(self.temp_dir / "data.csv", index=False)

        try:
            # 创建并启动容器
            self.container = docker.DockerClient().containers.run(
                self.image,
                command=["python", "/executor.py"],
                volumes={str(self.temp_dir): {"bind": "/data"}},
                detach=True,
                network_mode="none",  # 禁用网络访问
                mem_limit=self.memory_limit,
                cpu_shares=self.cpu_shares,
                working_dir="/data",
                remove=True,
            )
            logger.opt(colors=True).info(f"已启动Docker容器: <c>{self.container.id}</>")
            logger.opt(colors=True).info(f"临时目录: <y><u>{escape_tag(self.temp_dir)}</></>")
        except Exception as e:
            raise RuntimeError(f"启动Docker容器失败: {e}") from e

    def stop(self) -> None:
        """停止并移除Docker容器"""
        if self.container:
            id = self.container.id
            logger.opt(colors=True).info(f"停止Docker容器: <c>{id}</>")
            try:
                self.container.stop(timeout=1)
                self.container = None
            except docker.errors.DockerException:
                logger.opt(colors=True).exception(f"停止Docker容器 <c>{id}</> 时出错")

        if self.temp_dir and self.temp_dir.exists():
            logger.opt(colors=True).info(f"清理临时目录: <y><u>{escape_tag(self.temp_dir)}</></>")
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None

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

        # 确保容器已启动
        if not self.container or not self.temp_dir:
            self.start()
            assert self.container and self.temp_dir, "容器启动失败"  # noqa: PT018

        logger.info(f"正在执行代码:\n{code}")
        (self.temp_dir / "input.py").write_text(code, encoding="utf-8")
        output_file = self.temp_dir / "output.json"
        while not output_file.exists():
            time.sleep(0.5)

        output_data = output_file.read_bytes()
        output_file.unlink()
        return parse_result(output_data)
