import ast
import contextlib
import io
import json
import os
import shutil
import tempfile
import traceback
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, TypedDict, assert_never

import docker
import docker.errors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CODE_TEMPLATE_HEADER = """\
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO
import json
import sys

# 配置中文支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

df = pd.read_csv("/data/data.csv")

"""

CODE_TEMPLATE_FOOTER = """\

result_data = {}

if 'result' in locals() or 'result' in globals():
    if isinstance(result, pd.DataFrame):
        result.to_csv('/data/result.csv', index=False)
        result_data['type'] = 'dataframe'
    elif isinstance(result, pd.Series):
        result.to_frame().to_csv('/data/result.csv')
        result_data['type'] = 'series'
        result_data['name'] = result.name if result.name else 'result'
    elif hasattr(result, '__array__'):
        result_data['type'] = 'array'
        result_data['data'] = result.tolist()
    else:
        result_data['type'] = 'other'
        try:
            result_data['data'] = str(result)
        except:
            result_data['data'] = "无法序列化的结果"

if plt.gcf().get_axes():
    plt.savefig('/data/figure.png', dpi=300, bbox_inches='tight')
    result_data['has_figure'] = True

with open('/data/result.json', 'w') as f:
    json.dump(result_data, f)
"""


class ExecuteResult(TypedDict):
    success: bool
    output: str
    error: str
    result: Any
    figure: BytesIO | None


def extract_result(result: ExecuteResult, temp_dir: Path) -> None:
    result_json_path = temp_dir / "result.json"
    if not result_json_path.exists():
        return

    with open(result_json_path, "r") as f:
        result_metadata = json.load(f)

    # 处理DataFrame结果
    match result_metadata.get("type"):
        case "dataframe" if (temp_dir / "result.csv").exists():
            result["result"] = pd.read_csv(temp_dir / "result.csv")
        case "series" if (temp_dir / "result.csv").exists():
            df_with_index = pd.read_csv(temp_dir / "result.csv", index_col=0)
            series_name = result_metadata.get("name", "result")
            result["result"] = df_with_index.iloc[:, 0]
            result["result"].name = series_name
        case "array":
            result["result"] = np.array(result_metadata["data"])
        case _:
            result["result"] = result_metadata.get("data")

    if result_metadata.get("has_figure", False) and (temp_dir / "figure.png").exists():
        result["figure"] = BytesIO((temp_dir / "figure.png").read_bytes())


def execute_code_in_docker(code: str, df: pd.DataFrame) -> ExecuteResult:
    """
    使用Docker隔离环境执行代码
    """
    try:
        ast.parse(code)
    except SyntaxError as err:
        raise ValueError(f"代码语法错误 (行 {err.lineno} 列 {err.offset}): {err.msg}")

    # 创建临时目录作为挂载点
    temp_dir = Path(tempfile.mkdtemp())
    container = None

    # 保存数据到CSV文件
    data_path = temp_dir / "data.csv"
    df.to_csv(data_path, index=False)

    code_path = temp_dir / "code.py"
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(CODE_TEMPLATE_HEADER)
        f.write(code)
        f.write(CODE_TEMPLATE_FOOTER)

    try:
        # 创建Docker客户端
        client = docker.DockerClient()
        image = os.getenv("DOCKER_RUNNER_IMAGE")
        assert image, "DOCKER_RUNNER_IMAGE must be set in .env file"

        # 运行Docker容器
        container = client.containers.run(
            image,
            command=["python", "/data/code.py"],
            volumes={str(temp_dir): {"bind": "/data", "mode": "rw"}},
            detach=True,
            network_mode="none",  # 禁用网络访问
            mem_limit="512m",  # 限制内存使用
            cpu_shares=2,  # 限制CPU使用
            working_dir="/data",
            stdout=True,
            stderr=True,
        )

        # 等待容器结束并获取输出
        container_output = container.wait(timeout=30)
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

        # 解析结果
        result: ExecuteResult = {
            "success": container_output["StatusCode"] == 0,
            "output": stdout,
            "error": stderr,
            "result": None,
            "figure": None,
        }
        extract_result(result, temp_dir)
        return result

    except Exception as err:
        return {
            "success": False,
            "output": "",
            "error": f"Docker 执行错误: {err!r}\n{traceback.format_exc()}",
            "result": None,
            "figure": None,
        }
    finally:
        shutil.rmtree(temp_dir)
        if container is not None:
            with contextlib.suppress(docker.errors.DockerException):
                container.remove(force=True, v=True)


def execute_code_with_exec(code: str, df: pd.DataFrame) -> ExecuteResult:
    # 创建一个隔离的命名空间
    namespace = {
        "df": df.copy(),
        "pd": pd,
        "np": __import__("numpy"),
        "plt": __import__("matplotlib.pyplot"),
    }

    # 添加中文支持
    plt.rcParams["font.sans-serif"] = [
        "SimHei",
        "DejaVu Sans",
        "Arial Unicode MS",
        "sans-serif",
    ]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False

    # 捕获标准输出
    output_buffer = io.StringIO()
    result: ExecuteResult = {
        "success": False,
        "output": "",
        "error": "",
        "result": None,
        "figure": None,
    }

    try:
        # 重定向标准输出
        with contextlib.redirect_stdout(output_buffer):
            # 执行代码
            compiled_code = compile(code, "<string>", "exec")
            exec(compiled_code, namespace)

        # 检查是否有图表
        if (fig := plt.gcf()).get_axes():
            b = BytesIO()
            fig.savefig(b, format="png")
            b.seek(0)
            result["figure"] = b

        # 捕获输出
        result["output"] = output_buffer.getvalue()

        # 如果代码定义了result变量，使用它作为结果
        if "result" in namespace:
            result["result"] = namespace["result"]

        result["success"] = True
    except Exception as e:
        result["error"] = f"执行错误: {str(e)}\n{traceback.format_exc()}"
    finally:
        # 只重置样式但保留字体设置
        current_font_config = {
            "font.sans-serif": plt.rcParams["font.sans-serif"],
            "font.family": plt.rcParams["font.family"],
            "axes.unicode_minus": plt.rcParams["axes.unicode_minus"],
        }
        plt.style.use("default")
        # 恢复字体设置
        plt.rcParams.update(current_font_config)

    return result


type ExecuteMode = Literal["exec", "docker"]


def execute_code(mode: ExecuteMode, code: str, df: pd.DataFrame) -> ExecuteResult:
    match mode:
        case "docker":
            return execute_code_in_docker(code, df)
        case "exec":
            return execute_code_with_exec(code, df)
        case x:
            assert_never(x)


def main():
    from dotenv import load_dotenv

    load_dotenv()

    df = pd.read_csv("test.csv")
    result = execute_code_in_docker('result = df["math"]', df)
    if result["success"]:
        print("\n执行成功:")
        print(result["output"])
        if result["result"] is not None:
            print("\n结果数据:")
            print(result["result"])
        if result["figure"] is not None:
            print("\n图表已生成")
            plt.figure()
            plt.imshow(plt.imread(result["figure"]), aspect="auto")
            plt.axis("off")
            plt.show()
    else:
        print("\n执行失败:")
        print(result["error"])


if __name__ == "__main__":
    main()
