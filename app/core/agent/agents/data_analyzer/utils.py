import itertools

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable

from app.const import STATE_DIR
from app.core.agent.events import fix_message_content
from app.core.agent.prompts.data_analyzer import PROMPTS
from app.core.agent.resume import resume_tool_call
from app.core.agent.sources import Sources
from app.core.chain.llm import LLM
from app.exception import AgentNotFound
from app.log import logger
from app.utils import escape_tag

from .schemas import DataAnalyzerAgentState


def resume_tool_calls(sources: Sources, messages: list[AnyMessage]) -> None:
    for tool_call in itertools.chain.from_iterable(
        m.tool_calls for m in messages if isinstance(m, AIMessage) and m.tool_calls
    ):
        try:
            resume_tool_call(tool_call, {"sources": sources})
        except Exception as e:
            logger.opt(colors=True, exception=True).warning(
                f"恢复工具调用时出错: <y>{escape_tag(tool_call['name'])}</> - {escape_tag(str(e))}"
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
                formatted.append(
                    f"工具调用结果({id}): {status=}\n"
                    f"<tool-call-result>\n{content!r}\n{artifact_info}</tool-call-result>"
                )

    conversations = f"<conversation>\n{'\n'.join(formatted) if formatted else '无对话记录'}\n</conversation>"
    return conversations, figures


def create_title_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[object, str]:
    conversation = format_conversation(messages, include_figures=False)[0]
    prompt = PROMPTS.create_title.format(conversation=conversation)
    return (lambda _: prompt) | llm


def summary_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[str, tuple[str, list[str]]]:
    def prompt(report_template: str) -> str:
        return PROMPTS.summary.format(
            conversation=conversation,
            tool_intro=PROMPTS.tool_intro,
            report_template=report_template,
        )

    conversation, figures = format_conversation(messages, include_figures=True)
    return prompt | llm | (lambda s: (s, figures))


def get_agent_random_state(session_id: str) -> int:
    state_file = STATE_DIR / f"{session_id}.json"
    if not state_file.exists():
        raise AgentNotFound(session_id)

    state = DataAnalyzerAgentState.model_validate_json(state_file.read_text(encoding="utf-8"))
    return state.sources_random_state
