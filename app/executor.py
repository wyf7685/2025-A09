import ast
import base64
import json
import os
import shutil
import tempfile
import time
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Self, TypedDict
from weakref import finalize

import numpy as np
import pandas as pd

import docker
import docker.errors
from app.log import logger
from app import tool

class ExecuteResult(TypedDict):
    success: bool
    output: str
    error: str
    result: Any
    figure: BytesIO | None


class CodeExecutor:
    """
    代码执行器类，生命周期内控制一个Docker容器
    """

    def __init__(
        self,
        df: pd.DataFrame,
        image: str | None = None,
        timeout: int = 30,
        memory_limit: str = "512m",
        cpu_shares: int = 2,
    ) -> None:
        """
        初始化代码执行器

        Args:
            image: Docker镜像名称，如果为None则使用环境变量DOCKER_RUNNER_IMAGE
            timeout: 代码执行超时时间（秒）
            memory_limit: 内存限制
            cpu_shares: CPU使用限制
        """
        image = image or os.getenv("DOCKER_RUNNER_IMAGE")
        if not image:
            raise ValueError("Docker镜像名称未指定，请设置DOCKER_RUNNER_IMAGE环境变量")
        self.image = image
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_shares = cpu_shares
        self.client = docker.DockerClient()
        self.container = None
        self.temp_dir = Path(tempfile.mkdtemp())

        df.to_csv(self.temp_dir / "data.csv", index=False)
        finalize(self, self.stop)
        finalize(self, shutil.rmtree, self.temp_dir)

    def __enter__(self) -> Self:
        """使用上下文管理器启动容器"""
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """退出上下文管理器时关闭容器"""
        self.stop()

    def start(self) -> None:
        """启动Docker容器"""
        if self.container:
            return

        try:
            # 创建并启动容器，但不执行任何命令
            self.container = self.client.containers.run(
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
            # 等待容器完全启动
            time.sleep(1)
            logger.info(f"已启动Docker容器: {self.container.id}")
        except Exception as e:
            raise RuntimeError(f"启动Docker容器失败: {e}") from e

    def stop(self) -> None:
        """停止并移除Docker容器"""
        if self.container:
            logger.info(f"正在停止Docker容器: {self.container.id}")
            try:
                self.container.stop(timeout=1)
                self.container = None
            except docker.errors.DockerException:
                logger.exception("停止Docker容器时出错")

    def execute(self, code: str) -> ExecuteResult:
        """
        在Docker容器中执行代码

        Args:
            code: 要执行的Python代码

        Returns:
            ExecuteResult: 执行结果
        """
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

        # 确保容器已启动
        if not self.container:
            self.start()
            assert self.container, "容器启动失败"

        logger.info(f"正在执行代码:\n{code}")
        (self.temp_dir / "input.py").write_text(code, encoding="utf-8")
        output_file = self.temp_dir / "output.json"
        while not output_file.exists():
            time.sleep(0.5)

        output_data = output_file.read_bytes()
        output_file.unlink()

        # 解析结果
        result: ExecuteResult = {
            "success": False,
            "output": "",
            "error": "",
            "result": None,
            "figure": None,
        }

        if output_data:
            try:
                execution_result: dict = json.loads(output_data.decode("utf-8"))

                # 填充结果
                result["success"] = execution_result.get("success", False)
                result["output"] = execution_result.get("output", "")
                result["error"] = execution_result.get("error", "")

                # 处理返回值
                if "result" in execution_result:
                    result_type = execution_result.get("result_type", "other")

                    if result_type == "dataframe":
                        result["result"] = pd.read_json(StringIO(execution_result["result"]), orient="split")
                    elif result_type == "series":
                        result["result"] = pd.read_json(StringIO(execution_result["result"]), typ="series")
                        if "series_name" in execution_result:
                            result["result"].name = execution_result["series_name"]
                    elif result_type == "array":
                        result["result"] = np.array(execution_result["result"])
                    else:
                        result["result"] = execution_result["result"]

                # 处理图表
                if execution_result.get("has_figure") and execution_result.get("figure_data"):
                    figure_data = base64.b64decode(execution_result["figure_data"])
                    result["figure"] = BytesIO(figure_data)

            except json.JSONDecodeError as e:
                result["error"] += f"\n解析结果时出错: {e}"

        return result


def format_result(result: ExecuteResult) -> str:
    """格式化执行结果为字符串"""
    if not result["success"]:
        return f"执行失败: {result['error']}"

    output_lines = []
    if result["output"]:
        output_lines.append(f"输出:\n{result['output']}")
    if result["result"] is not None:
        output_lines.append(f"结果:\n{result['result']}")
    if result["figure"] is not None:
        output_lines.append("[包含可视化图表]")

    return "\n".join(output_lines)


def execute_code(code: str, df: pd.DataFrame) -> ExecuteResult:
    with CodeExecutor(df) as executor:
        return executor.execute(code)
