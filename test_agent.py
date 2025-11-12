from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from app.core.agent import DataAnalyzerAgent
from app.core.agent.events import BufferedStreamEventReader, StreamEvent
from app.core.chain import rate_limiter
from app.core.datasource import create_file_source
from app.log import configure_logging, logger
from app.utils import configure_matplotlib, escape_tag

if TYPE_CHECKING:
    from app.core.agent.schemas import SourcesDict

configure_matplotlib()
configure_logging()


def log_event(event: StreamEvent) -> None:
    match event.type:
        case "llm_token":
            logger.opt(colors=True).info(f"<y>LLM 输出:</>\n{escape_tag(event.content)}")
        case "tool_call":
            logger.opt(colors=True).info(
                f"开始工具调用: <c>{event.id}</>\n{escape_tag(event.name)}({escape_tag(str(event.args))})"
            )
        case "tool_result":
            logger.opt(colors=True).info(f"工具调用结果: <c>{event.id}</>\n{escape_tag(str(event.result)[:1000])}")
        case "tool_error":
            logger.opt(colors=True).error(f"工具调用错误: <c>{event.id}</>\n{escape_tag(event.error)}")


async def prepare_agent() -> DataAnalyzerAgent:
    # See 飞桨/碳中和—工业废气排放检测
    test_data_dir = Path("data/test")
    sources: SourcesDict = {
        "train": create_file_source(test_data_dir / "train.csv", sep="\t"),
        "test": create_file_source(test_data_dir / "test.csv", sep="\t"),
    }
    async with anyio.create_task_group() as tg:
        for source in sources.values():
            tg.start_soon(source.get_full_async)

    limiter = rate_limiter(14)
    return await DataAnalyzerAgent.create(
        session_id="TEST",
        sources_dict=sources,
        pre_model_hook=limiter,
    )


async def test_agent() -> None:
    agent = await prepare_agent()

    state_file = Path("state.json")
    await agent.load_state(state_file)

    while user_input := input(">>> ").strip():
        reader = BufferedStreamEventReader()
        try:
            async for event in reader.aread(agent.stream(user_input)):
                log_event(event)
        except Exception:
            logger.exception("Agent 执行失败")
            continue

        # 保存 agent 状态
        await agent.save_state(state_file)

        await anyio.sleep(0.1)

    for model_id, model_path in agent.ctx.saved_models.items():
        logger.info(f"模型 {model_id} 已保存到: {model_path}")

    if input("是否生成总结报告? [y/N]: ").strip().lower() == "y":
        summary, figures = await agent.summary()
        logger.info(f"\n{summary}\n")
        logger.info(f"包含图表: {len(figures)}")


if __name__ == "__main__":
    from contextlib import suppress

    with suppress(KeyboardInterrupt):
        anyio.run(test_agent)
