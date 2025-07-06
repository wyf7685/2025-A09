from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from app.agent import DataAnalyzerAgent
from app.chain import get_chat_model
from app.chain.general_analysis import GeneralSummary, GeneralSummaryInput
from app.chain.llm import get_llm, rate_limiter
from app.log import logger
from app.utils import format_overview

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
    logger.info(f"model_paths: {agent.saved_model_paths}")

    if input("是否执行总结? (y/n): ").strip().lower() == "y":
        summary, figures = GeneralSummary(llm).invoke(GeneralSummaryInput(format_overview(df), agent.execution_results))
        logger.info(f"总结报告:\n{summary}")
        logger.info(f"生成的图表数: {len(figures)}")


# 分析电弧炉运行数据中的异常值
# 分析能源消耗影响因素
# 建模预测电弧炉的能量消耗

if __name__ == "__main__":
    test_agent()
