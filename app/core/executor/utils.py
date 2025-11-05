import base64
import json
from io import StringIO
from typing import Any, TypedDict

import numpy as np
import pandas as pd


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
        return deserialize_result(json.loads(data.decode("utf-8")))
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"解析结果时出错: {e}",
            "result": None,
            "figure": None,
        }


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
