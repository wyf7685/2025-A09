import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, overload

from langchain_core.messages import ToolCall

from app.core.agent.tools._registry import TOOL_NAMES
from app.log import logger

type ResumeCall = Callable[..., object]


@dataclass
class ResumableTool:
    name: str
    fn: ResumeCall
    params: list[str]


_RESUME_TOOL_REGISTRY: dict[str, ResumableTool] = {}


@overload
def resumable[C: ResumeCall](tool_name: str, /) -> Callable[[C], C]: ...
@overload
def resumable[C: ResumeCall](tool_name: str, fn: C, /) -> C: ...


def resumable(tool_name: str, fn: ResumeCall | None = None, /) -> Callable[[ResumeCall], ResumeCall] | ResumeCall:
    """
    装饰器，用于注册可恢复的工具函数
    """

    def decorator(fn: ResumeCall) -> ResumeCall:
        # 规范化工具名称（移除首尾空格）
        normalized_name = tool_name.strip()

        # 记录注册信息
        # logger.info(f"注册工具: {normalized_name}")

        # 从TOOL_NAMES中获取所有可能的工具名称
        for func_name, name in TOOL_NAMES.items():
            if name == normalized_name or name.replace(" ", "") == normalized_name.replace(" ", ""):
                logger.info(f"找到工具名称匹配: {func_name} -> {name}")
                _RESUME_TOOL_REGISTRY[name] = ResumableTool(
                    name=name,
                    fn=fn,
                    params=list(inspect.signature(fn).parameters),
                )

                # 同时注册函数名作为工具名称
                if func_name not in _RESUME_TOOL_REGISTRY:
                    logger.info(f"同时注册函数名称: {func_name}")
                    _RESUME_TOOL_REGISTRY[func_name] = ResumableTool(
                        name=name,
                        fn=fn,
                        params=list(inspect.signature(fn).parameters),
                    )

                # 注册无空格版本的工具名称
                no_space_name = name.replace(" ", "")
                if no_space_name != name and no_space_name not in _RESUME_TOOL_REGISTRY:
                    logger.info(f"同时注册无空格版本工具名称: {no_space_name}")
                    _RESUME_TOOL_REGISTRY[no_space_name] = ResumableTool(
                        name=name,
                        fn=fn,
                        params=list(inspect.signature(fn).parameters),
                    )

        # 注册工具
        _RESUME_TOOL_REGISTRY[normalized_name] = ResumableTool(
            name=normalized_name,
            fn=fn,
            params=list(inspect.signature(fn).parameters),
        )

        # 注册函数名称
        _RESUME_TOOL_REGISTRY[fn.__name__] = ResumableTool(
            name=normalized_name,
            fn=fn,
            params=list(inspect.signature(fn).parameters),
        )

        # 同时注册无空格版本的工具名称，确保更好的兼容性
        no_space_name = normalized_name.replace(" ", "")
        if no_space_name != normalized_name and no_space_name not in _RESUME_TOOL_REGISTRY:
            logger.info(f"同时注册无空格版本工具名称: {no_space_name}")
            _RESUME_TOOL_REGISTRY[no_space_name] = ResumableTool(
                name=normalized_name,
                fn=fn,
                params=list(inspect.signature(fn).parameters),
            )

        return fn

    return decorator if fn is None else decorator(fn)


def is_resumable_tool(name: str) -> bool:
    return name in _RESUME_TOOL_REGISTRY


def resume_tool_call(tool_call: ToolCall, extra: dict[str, Any]) -> Any:
    """
    恢复工具调用

    参数:
        tool_call: 工具调用对象或字典
        extra: 额外参数

    返回:
        工具执行结果
    """
    # 获取工具名称
    name = tool_call["name"] if isinstance(tool_call, dict) else tool_call.name

    # 打印当前注册工具总数
    # logger.info(f"当前已注册的工具数量: {len(_RESUME_TOOL_REGISTRY)}")

    # 工具名称映射表（旧名称 -> 新名称）
    tool_name_mappings = {
        # 常见的工具名称映射
        "analyze_data": "通用数据分析工具",
        "inspect_dataframe_tool": "查看数据集状态",
        "infer_and_convert_dtypes_tool": "推断并转换数据类型",
        "create_column_tool": "创建新列",
        "correlation_analysis_tool": "相关性分析",
        "handle_missing_values_tool": "处理缺失值",
        "get_missing_values_summary_tool": "获取缺失值摘要",
        "fix_misaligned_data_tool": "修复数据错位",
    }

    # 添加常用工具的反向映射（使用工具名称本身作为键）
    analyze_data_mapping = {
        "analyze_data": "analyze_data",
        "通用数据分析工具": "analyze_data",
        "数据分析工具": "analyze_data",
        "分析数据": "analyze_data",
    }
    tool_name_mappings.update(analyze_data_mapping)

    # 添加常用工具的反向映射（使用工具名称本身作为键）
    inspect_df_mapping = {
        "inspect_dataframe_tool": "inspect_dataframe_tool",
        "查看数据集状态": "inspect_dataframe_tool",
        "数据集状态": "inspect_dataframe_tool",
        "查看数据框": "inspect_dataframe_tool",
        "数据预览": "inspect_dataframe_tool",
    }
    tool_name_mappings.update(inspect_df_mapping)

    # 从TOOL_NAMES构建更全的映射表
    for func_name, registered_name in TOOL_NAMES.items():
        if func_name not in tool_name_mappings:
            tool_name_mappings[func_name] = registered_name

    # 尝试直接匹配
    if r := _RESUME_TOOL_REGISTRY.get(name):
        logger.info(f"找到直接匹配的工具: {name}")
        args = {**tool_call["args"], **extra} if isinstance(tool_call, dict) else {**tool_call.args, **extra}
        return r.fn(**{k: v for k, v in args.items() if k in r.params})

    # 尝试映射工具名称
    mapped_name = tool_name_mappings.get(name, name)
    logger.info(f"工具名称映射: {name} -> {mapped_name}")

    # 尝试通过精确匹配查找注册的工具
    if r := _RESUME_TOOL_REGISTRY.get(mapped_name):
        logger.info(f"找到精确匹配的工具: {mapped_name}")
        args = {**tool_call["args"], **extra} if isinstance(tool_call, dict) else {**tool_call.args, **extra}
        return r.fn(**{k: v for k, v in args.items() if k in r.params})

    # 如果精确匹配失败，尝试模糊匹配（忽略空格）
    for registered_name, registered_tool in _RESUME_TOOL_REGISTRY.items():
        # 移除所有空格后比较
        if registered_name.replace(" ", "") == mapped_name.replace(" ", ""):
            logger.info(f"找到模糊匹配的工具: {registered_name}")
            args = {**tool_call["args"], **extra} if isinstance(tool_call, dict) else {**tool_call.args, **extra}
            return registered_tool.fn(**{k: v for k, v in args.items() if k in registered_tool.params})

    # 尝试基于工具名称前缀的模糊匹配（处理常见前缀/后缀）
    name_lower = name.lower()
    for registered_name, registered_tool in _RESUME_TOOL_REGISTRY.items():
        registered_lower = registered_name.lower()
        # 检查是否有工具名前缀或后缀匹配
        if (
            name_lower.startswith(registered_lower)
            or registered_lower.startswith(name_lower)
            or name_lower.endswith(registered_lower)
            or registered_lower.endswith(name_lower)
            or name_lower.replace("_tool", "") == registered_lower
            or registered_lower.replace("_tool", "") == name_lower
        ):
            logger.info(f"找到前缀/后缀匹配的工具: {registered_name}")
            args = {**tool_call["args"], **extra} if isinstance(tool_call, dict) else {**tool_call.args, **extra}
            return registered_tool.fn(**{k: v for k, v in args.items() if k in registered_tool.params})

    # 如果无法匹配，提供更详细的诊断信息
    logger.warning(f"工具 {name} 未找到匹配")
    return None
