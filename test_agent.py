from pathlib import Path

from app.core.agent import DataAnalyzerAgent
from app.core.agent.events import BufferedStreamEventReader, StreamEvent
from app.core.chain import get_chat_model, get_llm, rate_limiter
from app.core.datasource import create_csv_source
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
            logger.opt(colors=True).info(f"工具调用结果: <c>{event.id}</>\n{escape_tag(str(event.result))}")
        case "tool_error":
            logger.opt(colors=True).error(f"工具调用错误: <c>{event.id}</>\n{escape_tag(event.error)}")


def test_agent() -> None:
    # 速率限制
    limiter = rate_limiter(14)
    llm = limiter | get_llm()

    data_source = create_csv_source(Path("test.csv"))
    agent = DataAnalyzerAgent(
        data_source=data_source,
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
            for event in agent.stream(user_input):
                for evt in reader.push(event):
                    log_event(evt)
            if evt := reader.flush():
                log_event(evt)
        except Exception:
            logger.exception("Agent 执行失败")
            continue

        # 保存 agent 状态
        agent.save_state(state_file)

    for model_id, model_info in agent.trained_models.items():
        logger.info(f"模型 ID: {model_id}")
        logger.info(f"  模型类型: {model_info['model_type']}")
        logger.info(f"  特征列: {model_info['feature_columns']}")
        logger.info(f"  目标列: {model_info['target_column']}")
        if le := model_info.get("label_encoder"):
            logger.info(f"  标签编码器类别: {le['classes']}")
    for model_id, model_path in agent.saved_models.items():
        logger.info(f"模型 {model_id} 已保存到: {model_path}")

    if input("是否生成总结报告? [y/N]: ").strip().lower() == "y":
        summary, figures = agent.summary()
        logger.info(f"\n{summary}\n")
        logger.info(f"包含图表: {len(figures)}")


if __name__ == "__main__":
    test_agent()
