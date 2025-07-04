"""
Docker容器内执行Python代码的脚本
从/tmp/input.py读取代码，执行后将结果输出到/tmp/output.json
"""

import base64
import contextlib
import json
import time
import traceback
from io import BytesIO, StringIO
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.font_manager import FontProperties

# 配置中文支持
plt.rcParams["font.sans-serif"] = [
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "SimHei",
    "DejaVu Sans",
    "Arial Unicode MS",
    "sans-serif",
]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

context = {
    "pd": pd,
    "np": np,
    "plt": plt,
    "mpl": mpl,
    "__builtins__": __builtins__,
}


def execute_code(code: str) -> dict:
    # 初始化结果字典
    result = {"success": True, "output": "", "error": "", "result": None, "has_figure": False, "figure_data": None}

    # 捕获标准输出和错误
    mystdout = StringIO()
    mystderr = StringIO()

    try:
        # 执行代码
        compiled_code = compile(code, "<string>", "exec")
        with (
            contextlib.redirect_stdout(mystdout),
            contextlib.redirect_stderr(mystderr),
        ):
            exec(compiled_code, context)  # noqa: S102

        # 检查是否有图表
        if plt.gcf().get_axes():
            # 应用字体到所有文本元素
            for ax in plt.gcf().get_axes():
                for text in [*ax.texts, ax.title, ax.xaxis.label, ax.yaxis.label]:
                    text.set_fontproperties(FontProperties(family="sans-serif", size=text.get_fontsize()))

                # 设置刻度标签字体
                for label in ax.get_xticklabels() + ax.get_yticklabels():
                    label.set_fontproperties(FontProperties(family="sans-serif", size=label.get_fontsize()))

            # 将图表保存为base64编码的字符串
            img_buffer = BytesIO()
            plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
            img_buffer.seek(0)
            result["has_figure"] = True
            result["figure_data"] = base64.b64encode(img_buffer.read()).decode("utf-8")
            plt.close()

        # 检查是否有返回值
        if "result" in context:
            if isinstance(context["result"], pd.DataFrame):
                result["result_type"] = "dataframe"
                result["result"] = context["result"].to_json(orient="split")
            elif isinstance(context["result"], pd.Series):
                result["result_type"] = "series"
                result["result"] = context["result"].to_json()
                result["series_name"] = context["result"].name
            elif hasattr(context["result"], "__array__"):
                result["result_type"] = "array"
                result["result"] = context["result"].tolist()
            else:
                result["result_type"] = "other"
                result["result"] = str(context["result"])

    except Exception as e:
        result["success"] = False
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result["output"] = mystdout.getvalue()
    if (stderr := mystderr.getvalue()):
        result["error"] += stderr
    return result


if __name__ == "__main__":
    context["df"] = pd.read_csv("/data/data.csv")
    input_file = Path("/data/input.py")
    output_file = Path("/data/output.json")
    while True:
        if not input_file.exists():
            time.sleep(0.5)
            continue
        code = input_file.read_text(encoding="utf-8")
        input_file.unlink()
        result = execute_code(code)
        output_file.write_text(json.dumps(result), encoding="utf-8")
