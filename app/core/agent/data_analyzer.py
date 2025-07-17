import functools
import threading
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableLambda, ensure_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from app.core.agent.events import StreamEvent, fix_message_content, process_stream_event
from app.core.agent.schemas import (
    AgentValues,
    DataAnalyzerAgentState,
    DatasetID,
    Sources,
    format_sources_overview,
    sources_fn,
)
from app.core.agent.tools import analyzer_tool, dataframe_tools, scikit_tools, sources_tools
from app.core.agent.tools.dataframe.columns import create_aggregated_feature, create_column, create_interaction_term
from app.core.chain.llm import LLM
from app.log import logger
from app.schemas.session import SessionID
from app.utils import escape_tag

PROMPT_DIR = Path(__file__).parent / "prompts" / "data_analyzer"


def _read_prompt_file(filename: str) -> str:
    """读取指定的提示文件内容"""
    return (PROMPT_DIR / filename).read_text(encoding="utf-8")


TOOL_INTRO = _read_prompt_file("tool_intro.md")
SYSTEM_PROMPT = _read_prompt_file("system.md")
CREATE_TITLE_PROMPT = _read_prompt_file("create_title.md")
SUMMARY_PROMPT = _read_prompt_file("summary.md")


TOOLS_TO_RESUME = {
    "create_column_tool": create_column,
    "create_interaction_term_tool": create_interaction_term,
    "create_aggregated_feature_tool": create_aggregated_feature,
}


def resume_tool_calls(sources: Sources, messages: list[AnyMessage]) -> None:
    all_tool_calls = functools.reduce(
        (lambda a, b: a + b),
        (m.tool_calls for m in messages if isinstance(m, AIMessage) and m.tool_calls),
    )

    if not all_tool_calls:
        return

    for call in all_tool_calls:
        if tool := next((tool for name, tool in TOOLS_TO_RESUME.items() if name in call["name"]), None):
            logger.opt(colors=True).info(
                f"恢复工具调用: <y>{escape_tag(call['name'])}</> - {escape_tag(str(call['args']))}"
            )
            try:
                dataset_id = cast("DatasetID", call["args"]["dataset_id"])
                result = tool(df=sources[dataset_id].get_full(), **call["args"])
            except Exception as err:
                logger.opt(colors=True, exception=True).warning(
                    f"工具调用恢复失败: <y>{escape_tag(call['name'])}</> - {escape_tag(str(err))}"
                )
                continue
            if not result["success"]:
                logger.opt(colors=True).warning(
                    f"工具调用恢复失败: <y>{escape_tag(call['name'])}</> - {escape_tag(result['message'])}"
                )


def format_conversation(messages: list[AnyMessage], *, include_figures: bool) -> tuple[str, list[str]]:
    """格式化对话记录为字符串"""
    formatted: list[str] = []
    figures: list[str] = []
    for message in messages:
        match message:
            case HumanMessage(content=content):
                formatted.append(f"用户:\n<user-content>\n{content}\n</user-content>")
            case AIMessage(content=content, tool_calls=tool_calls):
                content = fix_message_content(content)
                formatted.append(f"AI:\n<ai-content>\n{content}\n</ai-content>")
                for tool_call in tool_calls:
                    if tool_call["id"] is None:
                        continue
                    formatted.append(
                        f"工具调用请求({tool_call['id']}): {tool_call['name']}\n"
                        f"<tool-call-args>\n{tool_call['args']!r}\n</tool-call-args>"
                    )
            case ToolMessage(tool_call_id=id, status=status, content=content, artifact=artifact):
                artifact_info = ""
                if (
                    include_figures
                    and isinstance(artifact, dict)
                    and artifact.get("type") == "image"
                    and (base64_data := artifact.get("base64_data")) is not None
                ):
                    artifact_info = f"[包含图片输出, ID={len(figures)}]\n"
                    figures.append(base64_data)
                formatted.append(f"工具调用结果({id}): {status}\n<tool-call>\n{content!r}\n{artifact_info}</tool-call>")

    return f"<conversation>\n{'\n'.join(formatted) if formatted else '无对话记录'}\n</conversation>", figures


def _create_title_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[object, str]:
    input = {"conversation": format_conversation(messages, include_figures=False)[0]}
    prompt = PromptTemplate(template=CREATE_TITLE_PROMPT, input_variables=["conversation"])
    return (lambda _: input) | prompt | llm


def _summary_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[object, tuple[str, list[str]]]:
    conversation, figures = format_conversation(messages, include_figures=True)
    prompt = PromptTemplate(template=SUMMARY_PROMPT, input_variables=["conversation", "tool_intro"])
    params = {"conversation": conversation, "tool_intro": TOOL_INTRO}
    return (lambda _: params) | prompt | llm | (lambda s: (s, figures))


class DataAnalyzerAgent:
    def __init__(
        self,
        sources: Sources,
        llm: LLM,
        chat_model: BaseChatModel,
        session_id: SessionID,
        *,
        # for rate limiting
        pre_model_hook: RunnableLambda | None = None,
    ) -> None:
        self.sources = sources
        self.llm = llm
        self.session_id = session_id

        get_df, create_df, rename_df = sources_fn(sources)
        analyzer = analyzer_tool(sources, llm)
        df_tools = dataframe_tools(get_df, create_df, rename_df)
        sk_tools, models, saved_models = scikit_tools(get_df, create_df, session_id)
        sc_tools = sources_tools(sources)
        all_tools = [analyzer, *df_tools, *sk_tools, *sc_tools]

        self.agent = create_react_agent(
            model=chat_model,
            tools=all_tools,
            prompt=SYSTEM_PROMPT.format(
                overview=format_sources_overview(sources),
                tool_intro=TOOL_INTRO,
            ),
            checkpointer=InMemorySaver(),
            pre_model_hook=pre_model_hook,
        )
        self.config = ensure_config({"recursion_limit": 200, "configurable": {"thread_id": threading.get_ident()}})
        self.trained_models = models
        self.saved_models = saved_models

        logger.info(f"创建数据分析 Agent: <y>{self.session_id}</>, 使用工具数: <y>{len(all_tools)}</>")

    def get_messages(self) -> list[AnyMessage]:
        """获取当前 agent 的对话记录"""
        return self.agent.get_state(self.config).values["messages"]

    def create_title(self) -> str:
        return _create_title_chain(self.llm, self.get_messages()).invoke(...)

    async def create_title_async(self) -> str:
        return await _create_title_chain(self.llm, self.get_messages()).ainvoke(...)

    def summary(self) -> tuple[str, list[str]]:
        return _summary_chain(self.llm, self.get_messages()).invoke(...)

    async def summary_async(self) -> tuple[str, list[str]]:
        return await _summary_chain(self.llm, self.get_messages()).ainvoke(...)

    def load_state(self, state_file: Path) -> None:
        """从指定的状态文件加载 agent 状态。"""
        if not state_file.exists():
            return

        try:
            state = DataAnalyzerAgentState.model_validate_json(state_file.read_bytes())
        except ValueError:
            logger.warning("无法加载 agent 状态: 状态文件格式错误")
            return

        self.agent.update_state(self.config, state.values)
        self.saved_models.update(state.models)
        resume_tool_calls(self.sources, state.values["messages"])
        logger.opt(colors=True).info(f"已加载 agent 状态: <y>{len(state.values['messages'])}</>")

    def save_state(self, state_file: Path) -> None:
        """将当前 agent 状态保存到指定的状态文件。"""
        state = DataAnalyzerAgentState(
            values=cast("AgentValues", self.agent.get_state(self.config).values),
            models=self.saved_models,
        )
        state_file.write_bytes(state.model_dump_json().encode("utf-8"))
        logger.opt(colors=True).info(f"已保存 agent 状态: <y>{len(state.values['messages'])}</>")

    def stream(self, user_input: str) -> Iterator[StreamEvent]:
        """使用用户输入调用 agent，并以流式方式返回事件"""
        for event in self.agent.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config,
            stream_mode="messages",
        ):
            yield from process_stream_event(event)

    async def astream(self, user_input: str) -> AsyncIterator[StreamEvent]:
        """异步使用用户输入调用 agent，并以流式方式返回事件"""
        async for event in self.agent.astream(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config,
            stream_mode="messages",
        ):
            for evt in process_stream_event(event):
                yield evt
