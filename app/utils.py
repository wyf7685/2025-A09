import contextlib
import functools
import importlib
import inspect
import platform
import re
import threading
from collections.abc import Callable, Coroutine
from typing import Any, cast

import anyio.to_thread
import matplotlib as mpl

mpl.use("Agg")  # 使用非交互式后端以避免GUI依赖

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties


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


def is_coroutine_callable(call: Callable[..., Any]) -> bool:
    """检查 call 是否是一个 callable 协程函数"""
    if inspect.isroutine(call):
        return inspect.iscoroutinefunction(call)
    if inspect.isclass(call):
        return False
    func_ = getattr(call, "__call__", None)  # noqa: B004
    return inspect.iscoroutinefunction(func_)


def run_sync[**P, R](call: Callable[P, R]) -> Callable[P, Coroutine[None, None, R]]:
    """一个用于包装 sync function 为 async function 的装饰器

    参数:
        call: 被装饰的同步函数
    """

    @functools.wraps(call)
    async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return await anyio.to_thread.run_sync(functools.partial(call, *args, **kwargs), abandon_on_cancel=True)

    return _wrapper


def resolve_dot_notation(obj_str: str, default_attr: str | None = None, default_prefix: str | None = None) -> Any:
    """解析并导入点分表示法的对象"""
    modulename, _, attrs = obj_str.partition(":")
    if default_prefix is not None and modulename.startswith("~"):
        modulename = default_prefix + modulename[1:]
    module = importlib.import_module(modulename)
    if not attrs:
        if default_attr is None:
            raise ImportError(f"'{obj_str}' does not specify an attribute to import.")
        return getattr(module, default_attr)
    instance = module
    for attr_str in attrs.split("."):
        instance = getattr(instance, attr_str)
    return instance


def escape_tag(s: object) -> str:
    """用于记录带颜色日志时转义 `<tag>` 类型特殊标签

    参考: [loguru color 标签](https://loguru.readthedocs.io/en/stable/api/logger.html#color)

    参数:
        s: 需要转义的字符串
    """
    return re.sub(r"</?((?:[fb]g\s)?[^<>\s]*)>", r"\\\g<0>", str(s))


def with_semaphore[T: Callable](initial_value: int) -> Callable[[T], T]:
    def decorator(func: T) -> T:
        if inspect.iscoroutinefunction(func):
            sem = anyio.Semaphore(initial_value)

            @functools.wraps(func)
            async def wrapper_async(*args: Any, **kwargs: Any) -> Any:
                async with sem:
                    return await func(*args, **kwargs)

            wrapper = wrapper_async
        else:
            sem = threading.Semaphore(initial_value)

            @functools.wraps(func)
            def wrapper_sync(*args: Any, **kwargs: Any) -> Any:
                with sem:
                    return func(*args, **kwargs)

            wrapper = wrapper_sync

        return cast("T", functools.update_wrapper(wrapper, func))

    return decorator


_ANSI_TO_LOGURU_TAG = {
    # Fore
    "\033[30m": "<black>",
    "\033[31m": "<red>",
    "\033[32m": "<green>",
    "\033[33m": "<yellow>",
    "\033[34m": "<blue>",
    "\033[35m": "<magenta>",
    "\033[36m": "<cyan>",
    "\033[37m": "<white>",
    # Back
    "\033[40m": "<BLACK>",
    "\033[41m": "<RED>",
    "\033[42m": "<GREEN>",
    "\033[43m": "<YELLOW>",
    "\033[44m": "<BLUE>",
    "\033[45m": "<MAGENTA>",
    "\033[46m": "<CYAN>",
    "\033[47m": "<WHITE>",
    # Style
    # "\033[0m": "</>",  # RESET
    "\033[1m": "<bold>",
    "\033[2m": "<dim>",
    "\033[3m": "<italic>",
    "\033[4m": "<underline>",
    "\033[5m": "<blink>",
    "\033[7m": "<reverse>",
    "\033[8m": "<hidden>",
    "\033[9m": "<strike>",
}
_ANSI_RESET = "\033[0m"
_ANSI_PATTERN = re.compile(r"(\033\[\d+(;\d+)*m)")


def ansi_to_loguru_tag(text: str) -> str:
    result: list[str] = []
    open_tags: list[str] = []
    last_end = 0

    for match in _ANSI_PATTERN.finditer(text):
        start, end = match.start(), match.end()
        ansi_code = text[start:end]

        if start > last_end:
            result.append(text[last_end:start])

        if ansi_code == _ANSI_RESET:
            result.append("</>" * len(open_tags))
            open_tags = []
        elif ansi_code in _ANSI_TO_LOGURU_TAG:
            loguru_tag = _ANSI_TO_LOGURU_TAG[ansi_code]
            result.append(loguru_tag)
            open_tags.append(loguru_tag)

        last_end = end

    if last_end < len(text):
        result.append(text[last_end:])

    return "".join(result)


def copy_param_annotations[**P, R](_: Callable[P, object], /) -> Callable[[Callable[..., R]], Callable[P, R]]:
    def decorator(fn: Callable[..., R]) -> Callable[P, R]:
        return cast("Callable[P, R]", fn)

    return decorator


def copy_signature[**P, R](_: Callable[P, R], /) -> Callable[[Callable[..., object]], Callable[P, R]]:
    def decorator(fn: Callable[..., object]) -> Callable[P, R]:
        return cast("Callable[P, R]", fn)

    return decorator
