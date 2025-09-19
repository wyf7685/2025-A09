import datetime
import threading
from collections.abc import Callable
from typing import Any, Literal, overload

import anyio.to_thread
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import SecretStr

from app.core.config import settings
from app.log import logger
from app.schemas.custom_model import LLModelID
from app.services.custom_model import custom_model_manager

type LLM = Runnable[LanguageModelInput, str]


def rate_limiter(max_call_per_minute: int) -> Runnable[Any, Any]:
    calls: list[datetime.datetime] = []
    delta = datetime.timedelta(minutes=1)

    @RunnableLambda
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

    return limiter


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


@overload
def _select_model(model_id: LLModelID, type: Literal["LLM"]) -> LLM: ...
@overload
def _select_model(model_id: LLModelID, type: Literal["ChatModel"]) -> BaseChatModel: ...
@overload
def _select_model(model_id: LLModelID, type: Literal["ALL"]) -> tuple[LLM, BaseChatModel]: ...


def _select_model(
    model_id: LLModelID,
    type: Literal["LLM", "ChatModel", "ALL"],  # noqa: A002
) -> LLM | BaseChatModel | tuple[LLM, BaseChatModel]:
    logger.debug(f"选择模型: {model_id} {type=}")
    model_name = model_id or settings.TEST_MODEL_NAME

    # 优先检查是否是自定义模型
    if custom_model_manager.is_custom_model(model_name):
        try:
            if config := custom_model_manager.get_model(model_name):
                logger.info(f"使用自定义模型: {config.name} ({config.provider})")

                # 根据提供商选择正确的模型类
                if config.provider.lower() == "google":
                    from langchain_google_genai import ChatGoogleGenerativeAI

                    chat_model = ChatGoogleGenerativeAI(
                        model=config.api_model_name,
                        google_api_key=SecretStr(config.api_key),
                        transport="rest",
                        timeout=30,  # 30秒超时
                        max_retries=2,  # 最多重试2次
                    )
                elif config.provider.lower() in ["openai", "deepseek"]:
                    from langchain_openai import ChatOpenAI

                    chat_model = ChatOpenAI(
                        model=config.api_model_name,
                        api_key=SecretStr(config.api_key),
                        base_url=config.api_url,
                        timeout=30,  # 30秒超时
                        max_retries=2,  # 最多重试2次
                    )
                else:
                    # 默认使用 OpenAI 兼容格式
                    from langchain_openai import ChatOpenAI

                    chat_model = ChatOpenAI(
                        model=config.api_model_name,
                        api_key=SecretStr(config.api_key),
                        base_url=config.api_url,
                        timeout=30,  # 30秒超时
                        max_retries=2,  # 最多重试2次
                    )
                return _convert_model(type, None, chat_model)
        except Exception as e:
            logger.error(f"创建自定义模型失败: {e}")
            logger.warning("回退到环境变量配置")

    # 如果不是自定义模型，检查是否有对应的自定义配置
    # 尝试查找具有相同模型名称的自定义配置
    all_custom_models = custom_model_manager.list_models()
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
            try:
                # 根据提供商选择正确的模型类
                if custom_config.provider.lower() == "google":
                    from langchain_google_genai import ChatGoogleGenerativeAI

                    chat_model = ChatGoogleGenerativeAI(
                        model=custom_config.api_model_name,
                        google_api_key=SecretStr(custom_config.api_key),
                        transport="rest",
                        timeout=30,  # 30秒超时
                        max_retries=2,  # 最多重试2次
                    )
                elif custom_config.provider.lower() in ["openai", "deepseek"]:
                    from langchain_openai import ChatOpenAI

                    chat_model = ChatOpenAI(
                        model=custom_config.api_model_name,
                        api_key=SecretStr(custom_config.api_key),
                        base_url=custom_config.api_url,
                        timeout=30,  # 30秒超时
                        max_retries=2,  # 最多重试2次
                    )
                else:
                    # 默认使用 OpenAI 兼容格式
                    from langchain_openai import ChatOpenAI

                    chat_model = ChatOpenAI(
                        model=custom_config.api_model_name,
                        api_key=SecretStr(custom_config.api_key),
                        base_url=custom_config.api_url,
                        timeout=30,  # 30秒超时
                        max_retries=2,  # 最多重试2次
                    )
                return _convert_model(type, None, chat_model)
            except Exception as e:
                logger.error(f"使用自定义配置创建模型失败: {e}")
                break

    # 如果没有找到自定义配置，记录警告并回退到环境变量
    logger.warning(f"未找到模型 '{model_name}' 的自定义配置，使用环境变量回退")

    # 原有的环境变量回退逻辑
    if model_name.startswith("gemini"):
        if settings.GOOGLE_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI

            logger.info(f"使用环境变量配置的 Google Generative AI 模型: {model_name}")
            return _convert_model(
                type,
                lambda: GoogleGenerativeAI(model=model_name, transport="rest"),
                lambda: ChatGoogleGenerativeAI(model=model_name, transport="rest"),
            )

        logger.warning("未配置 Google API Key，尝试其他回退选项")

    elif model_name.startswith(("gpt-", "claude-")):
        if settings.OPENAI_API_KEY and not settings.OPENAI_API_BASE:
            from langchain_openai import ChatOpenAI

            logger.info(f"使用环境变量配置的 OpenAI 模型: {model_name}")
            chat_model = ChatOpenAI(model=model_name)
            return _convert_model(type, None, chat_model)

        logger.warning("GPT/Claude模型需要真正的OpenAI API，当前环境变量配置不支持")

    elif model_name.startswith("deepseek"):
        if settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI

            logger.info(f"使用环境变量配置的 DeepSeek 模型: {model_name}")
            chat_model = ChatOpenAI(model=model_name, base_url="https://api.deepseek.com/v1")
            return _convert_model(type, None, chat_model)

        logger.warning("未配置 DeepSeek API Key (OPENAI_API_KEY)")

    # 最终回退到环境变量通用配置
    if settings.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI

        logger.info("使用环境变量配置的 Google Generative AI 作为最终回退")
        return _convert_model(
            type,
            lambda: GoogleGenerativeAI(model=model_name, transport="rest"),
            lambda: ChatGoogleGenerativeAI(model=model_name, transport="rest"),
        )

    if settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI

        logger.info("使用环境变量配置的 OpenAI 作为最终回退")
        chat_model = ChatOpenAI(model=model_name)
        return _convert_model(type, None, chat_model)

    # 最后的本地回退
    from langchain_ollama import ChatOllama, OllamaLLM

    logger.info("所有配置均未找到，尝试使用本地部署 Ollama 模型")
    return _convert_model(
        type,
        lambda: OllamaLLM(model=model_name),
        lambda: ChatOllama(model=model_name),
    )


def get_llm(model_id: LLModelID | None = None) -> LLM:
    return _select_model(model_id or settings.TEST_MODEL_NAME, "LLM")


async def get_llm_async(model_id: LLModelID | None = None) -> LLM:
    return await anyio.to_thread.run_sync(get_llm, model_id)


def get_chat_model(model_id: LLModelID | None = None) -> BaseChatModel:
    return _select_model(model_id or settings.TEST_MODEL_NAME, "ChatModel")


async def get_chat_model_async(model_id: LLModelID | None = None) -> BaseChatModel:
    return await anyio.to_thread.run_sync(get_chat_model, model_id)


def get_models(model_id: LLModelID | None = None) -> tuple[LLM, BaseChatModel]:
    return _select_model(model_id or settings.TEST_MODEL_NAME, "ALL")


async def get_models_async(model_id: LLModelID | None = None) -> tuple[LLM, BaseChatModel]:
    return await anyio.to_thread.run_sync(get_models, model_id)
