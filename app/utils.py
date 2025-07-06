import contextlib
import platform

import matplotlib as mpl

mpl.use("Agg")  # 使用非交互式后端以避免GUI依赖

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties


def format_overview(df: pd.DataFrame) -> str:
    return (
        f"数据规模: {df.shape[0]} 行 × {df.shape[1]} 列\n列数据类型:\n{df.dtypes}\n数据预览:\n{df.head().to_string()}"
    )


def configure_matplotlib_fonts() -> None:
    """配置matplotlib支持中文显示"""
    system = platform.system()

    if system == "Windows":
        # Windows系统常见中文字体
        font_names = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]
    elif system == "Linux":
        # Linux系统常见中文字体
        font_names = ["WenQuanYi Micro Hei", "WenQuanYi Zen Hei", "Noto Sans CJK SC", "Noto Sans CJK TC"]
    elif system == "Darwin":  # macOS
        # macOS系统常见中文字体
        font_names = ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS"]
    else:
        # 其他系统
        font_names = ["DejaVu Sans", "Arial Unicode MS"]

    # 尝试找到可用的中文字体
    chinese_font = None
    for font_name in font_names:
        with contextlib.suppress(Exception):
            font = FontProperties(family=font_name)
            if font.get_name() != "DejaVu Sans":  # 如果不是回退到默认字体
                chinese_font = font_name
                break

    if chinese_font:
        plt.rcParams["font.family"] = chinese_font
    else:
        # 如果没有找到中文字体，设置回退策略
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [*font_names, "sans-serif"]

    # 确保负号正确显示
    plt.rcParams["axes.unicode_minus"] = False


configure_matplotlib_fonts()
