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

    # 检查是否是自定义模型
    if custom_model_manager.is_custom_model(model_name):
        try:
            if config := custom_model_manager.get_model(model_name):
                logger.info(f"使用自定义模型: {config.name}")
                from langchain_openai import ChatOpenAI

                chat_model = ChatOpenAI(
                    model=config.model_name,
                    api_key=SecretStr(config.api_key),
                    base_url=config.api_url,
                )
                return _convert_model(type, None, chat_model)
        except Exception as e:
            logger.error(f"创建自定义模型失败: {e}")
            logger.warning("回退到默认模型")
        else:
            logger.warning(f"未找到自定义模型配置 {model_name}，回退到默认模型")

    if model_name.startswith("gemini"):
        if settings.GOOGLE_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI

            logger.info(f"使用 Google Generative AI 模型: {model_name}")
            return _convert_model(
                type,
                lambda: GoogleGenerativeAI(model=model_name, transport="rest"),
                lambda: ChatGoogleGenerativeAI(model=model_name, transport="rest"),
            )

        logger.warning("未配置 Google API Key，回退到默认模型")

    elif model_name.startswith(("gpt-", "claude-")):
        if settings.OPENAI_API_KEY and not settings.OPENAI_API_BASE:
            # 只有在使用真正的OpenAI API时才支持GPT模型
            from langchain_openai import ChatOpenAI

            logger.info(f"使用 OpenAI 模型: {model_name}")
            chat_model = ChatOpenAI(model=model_name)
            return _convert_model(type, None, chat_model)

        logger.warning("GPT/Claude模型需要真正的OpenAI API，当前配置不支持，回退到默认模型")

    elif model_name.startswith("deepseek"):
        if settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI

            logger.info(f"使用 DeepSeek 模型: {model_name}")
            chat_model = ChatOpenAI(model=model_name, base_url="https://api.deepseek.com/v1")
            return _convert_model(type, None, chat_model)

        logger.warning("未配置 DeepSeek API Key，回退到默认模型")

    # 回退到原有逻辑
    if settings.GOOGLE_API_KEY:
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI

        logger.info("使用 Google Generative AI 模型")
        return _convert_model(
            type,
            lambda: GoogleGenerativeAI(model=model_name, transport="rest"),
            lambda: ChatGoogleGenerativeAI(model=model_name, transport="rest"),
        )

    if settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI

        logger.info("使用 OpenAI 模型")
        chat_model = ChatOpenAI(model=model_name)
        return _convert_model(type, None, chat_model)

    # TODO: check Ollama api url
    from langchain_ollama import ChatOllama, OllamaLLM

    logger.info("未检测到模型配置，尝试使用本地部署 Ollama 模型")
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
