import datetime
import os
import threading
from typing import Any

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda, RunnableWithMessageHistory

from app.log import logger

type LLM = Runnable[LanguageModelInput, str]


def rate_limiter(max_call_per_minute: int) -> RunnableLambda[Any, Any]:
    calls: list[datetime.datetime] = []

    @RunnableLambda
    def limiter(input: Any) -> Any:
        calls.append(datetime.datetime.now())
        # 清理超过一分钟的调用记录
        calls[:] = [call for call in calls if call > datetime.datetime.now() - datetime.timedelta(minutes=1)]
        if len(calls) > max_call_per_minute:
            wait_time = 60 - (datetime.datetime.now() - calls[0]).total_seconds()
            if wait_time > 0:
                logger.warning(f"超过速率限制，等待 {wait_time:.2f} 秒")
                threading.Event().wait(wait_time)
                logger.info("等待结束，继续处理请求")

        if isinstance(input, dict):  # graph input (state)
            # remove keys to avoid warnings
            input.pop("is_last_step", None)
            input.pop("remaining_steps", None)
        return input

    return limiter


def get_llm() -> LLM:
    """获取配置的LLM实例"""
    model_name = os.environ.get("TEST_MODEL_NAME")
    assert model_name, "TEST_MODEL_NAME 环境变量未设置"

    if "GOOGLE_API_KEY" in os.environ:
        from langchain_google_genai import GoogleGenerativeAI

        logger.info("使用 Google Generative AI 模型")
        return GoogleGenerativeAI(model=model_name)

    if "OPENAI_API_KEY" in os.environ:
        from langchain_openai import ChatOpenAI

        logger.info("使用 OpenAI 模型")

        def convert(msg: BaseMessage) -> str:
            if isinstance(msg.content, str):
                return msg.content
            if isinstance(msg.content, list):
                return "\n".join(str(m) for m in msg.content)
            raise ValueError(f"Unsupported message content type: {type(msg.content)}")

        return ChatOpenAI(model=model_name) | convert

    # TODO: check Ollama api url
    from langchain_ollama import OllamaLLM

    logger.info("未检测到模型配置，尝试使用本地部署 Ollama 模型")
    return OllamaLLM(model=model_name)


def get_chat_model() -> BaseChatModel:
    model_name = os.environ.get("TEST_MODEL_NAME")
    assert model_name, "TEST_MODEL_NAME 环境变量未设置"

    if "GOOGLE_API_KEY" in os.environ:
        from langchain_google_genai import ChatGoogleGenerativeAI

        logger.info("使用 Google Generative AI 模型")
        return ChatGoogleGenerativeAI(model=model_name)

    if "OPENAI_API_KEY" in os.environ:
        from langchain_openai import ChatOpenAI

        logger.info("使用 OpenAI 模型")
        return ChatOpenAI(model=model_name)

    # TODO: check Ollama api url
    from langchain_ollama import ChatOllama

    logger.info("未检测到模型配置，尝试使用本地部署 Ollama 模型")
    return ChatOllama(model=model_name)


def wrap_with_memory(llm: LLM) -> LLM:
    history = InMemoryChatMessageHistory()
    return RunnableWithMessageHistory(llm, lambda: history)
