# ruff: noqa: E731
from __future__ import annotations

import datetime
import threading
from typing import TYPE_CHECKING, Any, Literal, overload

import anyio.to_thread
from pydantic import SecretStr

from app.log import logger
from app.services.custom_model import custom_model_manager
from app.utils import escape_tag

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import Runnable

    from app.schemas.custom_model import CustomModelConfig, LLModelID

type LLM = Runnable[LanguageModelInput, str]


def rate_limiter(max_call_per_minute: int) -> Runnable[Any, Any]:
    from langchain_core.runnables import RunnableLambda

    calls: list[datetime.datetime] = []
    delta = datetime.timedelta(minutes=1)

    def limiter(input: Any) -> Any:
        now = datetime.datetime.now()
        calls.append(now)
        # 清理超过一分钟的调用记录
        expired = now - delta
        calls[:] = [call for call in calls if call > expired]
        if len(calls) > max_call_per_minute:
            wait_time = 60 - (now - calls[0]).total_seconds()
            if wait_time > 0:
                logger.opt(colors=True).warning(f"超过速率限制，等待 <y>{wait_time:.2f}</> 秒")
                threading.Event().wait(wait_time)
                logger.info("等待结束，继续处理请求")

        if isinstance(input, dict):  # graph input (state)
            # remove keys to avoid warnings
            input.pop("is_last_step", None)
            input.pop("remaining_steps", None)
        return input

    return RunnableLambda(limiter)


def _convert(msg: BaseMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content
    if isinstance(msg.content, list):
        return "\n".join(str(m) for m in msg.content)
    raise ValueError(f"Unsupported message content type: {type(msg.content)}")


def _convert_model(
    type: Literal["LLM", "ChatModel", "ALL"],  # noqa: A002
    llm: Callable[[], LLM] | None,
    chat_model: BaseChatModel | Callable[[], BaseChatModel],
) -> LLM | BaseChatModel | tuple[LLM, BaseChatModel]:
    from langchain_core.language_models import BaseChatModel

    get_chat_model = (lambda: chat_model) if isinstance(chat_model, BaseChatModel) else chat_model

    match type:
        case "LLM" if llm:
            return llm()
        case "LLM":
            return get_chat_model() | _convert
        case "ChatModel":
            return get_chat_model()
        case "ALL":
            _chat_model = get_chat_model()
            return (llm() if llm else _chat_model | _convert), _chat_model


def _from_config(config: CustomModelConfig) -> tuple[Callable[[], LLM] | None, Callable[[], BaseChatModel]]:
    logger.opt(colors=True).info(
        f"使用自定义模型: <c>{escape_tag(config.name)}</> (<g>{escape_tag(config.provider)}</>)"
        f" - <y>{escape_tag(config.api_model_name)}</>",
    )

    temperature_kwargs: dict[str, Any] = {
        "temperature": 0.1,
    }
    timeout_retry_kwargs: dict[str, Any] = {
        "timeout": 30,  # 30秒超时
        "max_retries": 2,  # 最多重试2次
    }

    # 根据提供商选择正确的模型类
    if config.provider.lower() == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI

        llm = lambda: GoogleGenerativeAI(
            model=config.api_model_name,
            google_api_key=SecretStr(config.api_key),
            transport="rest",
            **temperature_kwargs,
            **timeout_retry_kwargs,
        )
        chat_model = lambda: ChatGoogleGenerativeAI(
            model=config.api_model_name,
            google_api_key=SecretStr(config.api_key),
            transport="rest",
            **temperature_kwargs,
            **timeout_retry_kwargs,
        )
    elif config.provider.lower() == "deepseek":
        from langchain_deepseek import ChatDeepSeek

        llm = None
        chat_model = lambda: ChatDeepSeek(
            model=config.api_model_name,
            api_key=SecretStr(config.api_key),
            base_url=config.api_url,
            **temperature_kwargs,
            **timeout_retry_kwargs,
        )
    elif config.provider.lower() == "ollama":
        from langchain_ollama import ChatOllama, OllamaLLM

        llm = lambda: OllamaLLM(
            model=config.api_model_name,
            base_url=config.api_url,
            **timeout_retry_kwargs,
        )
        chat_model = lambda: ChatOllama(
            model=config.api_model_name,
            base_url=config.api_url,
            **timeout_retry_kwargs,
        )
    elif config.provider.lower() == "zhipuai" or config.provider.lower() == "openai":
        from langchain_openai import ChatOpenAI, OpenAI

        llm = lambda: OpenAI(
            model=config.api_model_name,
            api_key=SecretStr(config.api_key),
            base_url=config.api_url,
            **temperature_kwargs,
            **timeout_retry_kwargs,
        )
        chat_model = lambda: ChatOpenAI(
            model=config.api_model_name,
            api_key=SecretStr(config.api_key),
            base_url=config.api_url,
            **temperature_kwargs,
            **timeout_retry_kwargs,
        )
    else:
        # 默认使用 OpenAI 兼容格式
        from langchain_openai import ChatOpenAI, OpenAI

        llm = None
        chat_model = lambda: ChatOpenAI(
            model=config.api_model_name,
            api_key=SecretStr(config.api_key),
            base_url=config.api_url,
            **temperature_kwargs,
            **timeout_retry_kwargs,
        )

    return llm, chat_model


@overload
def _select_model(model_id: LLModelID | None, type: Literal["LLM"]) -> LLM: ...
@overload
def _select_model(model_id: LLModelID | None, type: Literal["ChatModel"]) -> BaseChatModel: ...
@overload
def _select_model(model_id: LLModelID | None, type: Literal["ALL"]) -> tuple[LLM, BaseChatModel]: ...


def _select_model(
    model_id: LLModelID | None,
    type: Literal["LLM", "ChatModel", "ALL"],  # noqa: A002
) -> LLM | BaseChatModel | tuple[LLM, BaseChatModel]:
    logger.opt(colors=True).debug(f"选择模型: model_id=<c>{escape_tag(model_id)}</> type=<y>{escape_tag(type)}</>")
    if model_id is None:
        model_id = custom_model_manager.select_first_model_id()
    if model_id is None:
        raise ValueError("未提供模型ID，且没有可用的自定义模型")

    model_name = model_id

    # 优先检查是否是自定义模型
    if custom_model_manager.is_custom_model(model_name):
        try:
            if config := custom_model_manager.get_model(model_name):
                return _convert_model(type, *_from_config(config))
        except Exception as e:
            logger.error(f"创建自定义模型失败: {e}")
            logger.warning("回退到环境变量配置")

    # 如果不是自定义模型，检查是否有对应的自定义配置
    # 尝试查找具有相同模型名称的自定义配置
    all_custom_models = custom_model_manager.list_models()
    custom_config = None
    for custom_config in all_custom_models.values():
        # 更灵活的匹配逻辑：
        # 1. 直接匹配 model_name
        # 2. 匹配 name（显示名称）
        # 3. 忽略大小写和特殊字符的匹配
        model_name_normalized = model_name.lower().replace("-", " ").replace(".", " ")
        config_model_normalized = custom_config.model_name.lower().replace("-", " ").replace(".", " ")
        config_name_normalized = custom_config.name.lower().replace("-", " ").replace(".", " ")

        if (
            custom_config.model_name == model_name
            or custom_config.name == model_name
            or config_model_normalized == model_name_normalized
            or config_name_normalized == model_name_normalized
        ):
            logger.info(f"找到匹配的自定义配置: {custom_config.name} (匹配模型: {model_name})")
            break

    if custom_config is not None:
        try:
            return _convert_model(type, *_from_config(custom_config))
        except Exception as e:
            logger.error(f"使用自定义配置创建模型失败: {e}")

    raise ValueError(f"未找到模型 '{model_name}' 的自定义配置，请先添加自定义模型")


def get_llm(model_id: LLModelID | None = None) -> LLM:
    return _select_model(model_id, "LLM")


async def get_llm_async(model_id: LLModelID | None = None) -> LLM:
    return await anyio.to_thread.run_sync(get_llm, model_id)


def get_chat_model(model_id: LLModelID | None = None) -> BaseChatModel:
    return _select_model(model_id, "ChatModel")


async def get_chat_model_async(model_id: LLModelID | None = None) -> BaseChatModel:
    return await anyio.to_thread.run_sync(get_chat_model, model_id)


def get_models(model_id: LLModelID | None = None) -> tuple[LLM, BaseChatModel]:
    return _select_model(model_id, "ALL")


async def get_models_async(model_id: LLModelID | None = None) -> tuple[LLM, BaseChatModel]:
    return await anyio.to_thread.run_sync(get_models, model_id)
