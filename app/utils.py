import asyncio
import contextlib
import functools
import importlib
import platform
import re
from collections.abc import Callable, Coroutine
from typing import Any

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


def run_sync[**P, R](call: Callable[P, R]) -> Callable[P, Coroutine[None, None, R]]:
    """一个用于包装 sync function 为 async function 的装饰器

    参数:
        call: 被装饰的同步函数
    """

    @functools.wraps(call)
    async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return await asyncio.to_thread(functools.partial(call, *args, **kwargs))

    return _wrapper


def resolve_dot_notation(obj_str: str, default_attr: str, default_prefix: str | None = None) -> Any:
    """解析并导入点分表示法的对象"""
    modulename, _, cls = obj_str.partition(":")
    if default_prefix is not None and modulename.startswith("~"):
        modulename = default_prefix + modulename[1:]
    module = importlib.import_module(modulename)
    if not cls:
        return getattr(module, default_attr)
    instance = module
    for attr_str in cls.split("."):
        instance = getattr(instance, attr_str)
    return instance


def escape_tag(s: str) -> str:
    """用于记录带颜色日志时转义 `<tag>` 类型特殊标签

    参考: [loguru color 标签](https://loguru.readthedocs.io/en/stable/api/logger.html#color)

    参数:
        s: 需要转义的字符串
    """
    return re.sub(r"</?((?:[fb]g\s)?[^<>\s]*)>", r"\\\g<0>", s)
