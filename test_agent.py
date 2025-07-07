from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from app.core.agent import DataAnalyzerAgent
from app.core.chain import get_chat_model, get_llm, rate_limiter
from app.log import logger

load_dotenv()


def test_agent() -> None:
    # 读取数据
    df = pd.read_csv(Path("test.csv"), encoding="utf-8")

    # 速率限制
    limiter = rate_limiter(14)
    llm = limiter | get_llm()

    agent = DataAnalyzerAgent(df, llm, get_chat_model(), pre_model_hook=limiter)

    state_file = Path("state.json")
    agent.load_state(state_file)

    while user_input := input(">>> ").strip():
        try:
            for message in agent.invoke(user_input):
                content = message.content
                if isinstance(content, list):
                    content = "\n".join(str(item) for item in content)
                if content := content.strip():
                    logger.info(f"LLM输出:\n{content}")
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


if __name__ == "__main__":
    test_agent()
