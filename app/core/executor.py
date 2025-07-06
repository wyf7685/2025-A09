import ast
import base64
import json
import os
import shutil
import tempfile
import time
from io import StringIO
from pathlib import Path
from typing import Any, Self, TypedDict
from weakref import finalize

import numpy as np
import pandas as pd

import docker
import docker.errors
from app.log import logger


class ExecuteResult(TypedDict):
    success: bool
    output: str
    error: str
    result: Any
    figure: bytes | None


def serialize_result(result: ExecuteResult) -> dict:
    data = {}
    if isinstance(result["result"], pd.DataFrame):
        data["result_type"] = "dataframe"
        data["result"] = result["result"].to_json(orient="split")
    elif isinstance(result["result"], pd.Series):
        data["result_type"] = "series"
        data["result"] = result["result"].to_json()
        data["series_name"] = result["result"].name
    elif hasattr(result["result"], "__array__"):
        data["result_type"] = "array"
        data["result"] = result["result"].tolist()
    else:
        data["result_type"] = "other"
        data["result"] = str(result["result"])
    data["success"] = result["success"]
    data["output"] = result["output"]
    data["error"] = result["error"]
    if result["figure"] is not None:
        data["has_figure"] = True
        data["figure_data"] = base64.b64encode(result["figure"]).decode("utf-8")
    else:
        data["has_figure"] = False
        data["figure_data"] = None
    return data


def deserialize_result(data: dict) -> ExecuteResult:
    result: ExecuteResult = {
        "success": data.get("success", False),
        "output": data.get("output", ""),
        "error": data.get("error", ""),
        "result": None,
        "figure": None,
    }

    # 处理返回值
    if "result" in data:
        result_type = data.get("result_type", "other")
        if result_type == "dataframe":
            result["result"] = pd.read_json(StringIO(data["result"]), orient="split")
        elif result_type == "series":
            result["result"] = pd.read_json(StringIO(data["result"]), typ="series")
            if "series_name" in data:
                result["result"].name = data["series_name"]
        elif result_type == "array":
            result["result"] = np.array(data["result"])
        else:
            result["result"] = data["result"]

    # 处理图表
    if data.get("has_figure") and data.get("figure_data"):
        result["figure"] = base64.b64decode(data["figure_data"])

    return result


def parse_result(data: bytes) -> ExecuteResult:
    try:
        execution_result: dict = json.loads(data.decode("utf-8"))
        return deserialize_result(execution_result)
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"解析结果时出错: {e}",
            "result": None,
            "figure": None,
        }


class CodeExecutor:
    """
    代码执行器类，生命周期内控制一个Docker容器
    """

    def __init__(
        self,
        df: pd.DataFrame,
        image: str | None = None,
        memory_limit: str = "512m",
        cpu_shares: int = 2,
    ) -> None:
        """
        初始化代码执行器

        Args:
            image: Docker镜像名称，如果为None则使用环境变量DOCKER_RUNNER_IMAGE
            memory_limit: 内存限制
            cpu_shares: CPU使用限制
        """
        image = image or os.getenv("DOCKER_RUNNER_IMAGE")
        if not image:
            raise ValueError("Docker镜像名称未指定，请设置DOCKER_RUNNER_IMAGE环境变量")
        self.image = image
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
        return parse_result(output_data)


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
