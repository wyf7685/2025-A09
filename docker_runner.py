import ast
import traceback
from typing import Any
import docker
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tempfile
import json
from pathlib import Path


CODE_TEMPLATE_HEADER = """\
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO
import json
import sys

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
    plt.savefig('/data/figure.png')
    result_data['has_figure'] = True

with open('/data/result.json', 'w') as f:
    json.dump(result_data, f)
"""


def execute_code_in_docker(code: str, df: pd.DataFrame) -> dict[str, Any]:
    """
    使用Docker隔离环境执行代码
    """
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"代码语法错误 (行 {e.lineno} 列 {e.offset}): {e.msg}")

    # 创建临时目录作为挂载点
    temp_dir = Path(tempfile.mkdtemp())
    container = None

    try:
        # 保存数据到CSV文件
        data_path = temp_dir / "data.csv"
        df.to_csv(data_path, index=False)

        code_path = temp_dir / "code.py"
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(CODE_TEMPLATE_HEADER)
            f.write(code)
            f.write(CODE_TEMPLATE_FOOTER)

        # 创建Docker客户端
        client = docker.from_env()
        image = os.getenv("DOCKER_RUNNER_IMAGE")
        assert image, "DOCKER_RUNNER_IMAGE must be set in .env file"

        # 运行Docker容器
        container = client.containers.run(
            image,
            command="python /data/code.py",
            volumes={str(temp_dir): {"bind": "/data", "mode": "rw"}},
            detach=True,
            # remove=True,
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
        result = {
            "success": container_output["StatusCode"] == 0,
            "output": stdout,
            "error": stderr,
            "result": None,
            "figure": None,
        }

        # 检查结果文件
        result_json_path = temp_dir / "result.json"
        if result_json_path.exists():
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

            # 处理图表
            if (
                result_metadata.get("has_figure", False)
                and (temp_dir / "figure.png").exists()
            ):
                import matplotlib.image as mpimg

                result["figure"] = plt.figure()
                img = mpimg.imread(temp_dir / "figure.png")
                plt.imshow(img)
                plt.axis("off")

        return result

    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Docker执行错误: {str(e)}\n{traceback.format_exc()}",
            "result": None,
            "figure": None,
        }
    finally:
        # 清理临时文件
        import shutil

        shutil.rmtree(temp_dir)

        if container is not None:
            container.remove(force=True)


def main():
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
            result["figure"].show()
    else:
        print("\n执行失败:")
        print(result["error"])


if __name__ == "__main__":
    main()
