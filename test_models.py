# ruff: noqa: T201

from app.core.chain.llm import get_chat_model


def test_model_selection() -> None:
    """测试不同模型的选择"""

    # 测试各种模型
    models_to_test = ["gemini-2.0-flash", "gemini-1.5-pro", "gpt-4", "deepseek-r1:8b", "deepseek-r1:api"]

    print("测试模型选择功能...")
    print("=" * 50)

    for model_id in models_to_test:
        try:
            chat_model = get_chat_model(model_id)
            model_name = getattr(chat_model, "model", "Unknown")
            model_type = type(chat_model).__name__

            print(f"✅ 模型 {model_id}:")
            print(f"   - 类型: {model_type}")
            print(f"   - 实际模型名: {model_name}")
            print()

        except Exception as e:
            print(f"❌ 模型 {model_id} 失败:")
            print(f"   - 错误: {e}")
            print()


if __name__ == "__main__":
    test_model_selection()
