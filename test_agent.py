from pathlib import Path

from app.core.agent import DataAnalyzerAgent
from app.core.agent.events import BufferedStreamEventReader, StreamEvent
from app.core.agent.schemas import SourcesDict
from app.core.chain import get_chat_model, get_llm, rate_limiter
from app.core.datasource import create_file_source
from app.log import logger
from app.utils import escape_tag


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


def prefetch_data(sources: SourcesDict) -> None:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor() as executor:
        futures = {source_id: executor.submit(source.get_full) for source_id, source in sources.items()}
        for source_id, future in futures.items():
            try:
                future.result()
            except Exception:
                logger.exception(f"数据加载失败: {source_id}")


def test_agent() -> None:
    # 速率限制
    limiter = rate_limiter(14)
    llm = limiter | get_llm()

    # See 飞桨/碳中和—工业废气排放检测
    test_data_dir = Path("data/test")
    sources: SourcesDict = {
        "train": create_file_source(test_data_dir / "train.csv", sep="\t"),
        "test": create_file_source(test_data_dir / "test.csv", sep="\t"),
    }
    prefetch_data(sources)

    agent = DataAnalyzerAgent(
        sources_dict=sources,
        llm=llm,
        chat_model=get_chat_model(),
        session_id="TEST",
        pre_model_hook=limiter,
    )

    state_file = Path("state.json")
    agent.load_state(state_file)

    while user_input := input(">>> ").strip():
        reader = BufferedStreamEventReader()
        try:
            for event in reader(agent.stream(user_input)):
                log_event(event)
        except Exception:
            logger.exception("Agent 执行失败")
            continue

        # 保存 agent 状态
        agent.save_state(state_file)

    for model_id, model_path in agent.saved_models.items():
        logger.info(f"模型 {model_id} 已保存到: {model_path}")

    if input("是否生成总结报告? [y/N]: ").strip().lower() == "y":
        summary, figures = agent.summary()
        logger.info(f"\n{summary}\n")
        logger.info(f"包含图表: {len(figures)}")


if __name__ == "__main__":
    test_agent()
