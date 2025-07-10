#!/usr/bin/env python3
"""
测试会话命名功能
"""

import asyncio
import json
from pathlib import Path

import pandas as pd
import pytest

from app.api.v1.sessions import get_or_create_session, sessions
from app.api.v1.chat import clean_message_for_session_name


class TestSessionNaming:
    """测试会话命名功能"""

    def test_clean_message_for_session_name(self):
        """测试消息清理和截断功能"""
        test_cases = [
            # (输入消息, 期望的处理结果)
            ("请帮我分析这个数据集", "请帮我分析这个数据集"),
            ("如何训练一个机器学习模型？", "如何训练一个机器学习模型？"),
            ("   多余的空格测试   ", "多余的空格测试"),
            ("包含@#$%特殊字符的消息！！！", "包含特殊字符的消息"),
            ("", "未命名对话"),
            ("   ", "未命名对话"),
            # 测试长消息截断
            ("这是一个非常非常非常非常非常非常长的消息内容，应该被截断处理。", "这是一个非常非常非常非常非常非常长的消息内容，应该被截断..."),
            ("短消息。", "短消息。"),  # 在句号处截断
            ("这是测试？", "这是测试？"),  # 在问号处截断
        ]

        for input_msg, expected in test_cases:
            result = clean_message_for_session_name(input_msg)
            print(f"输入: {repr(input_msg)}")
            print(f"输出: {repr(result)}")
            print(f"期望: {repr(expected)}")
            if expected == "未命名对话":
                assert result == expected
            else:
                assert result.startswith(expected.split("...")[0].rstrip())
            print("✓ 通过\n")

    def test_session_creation_with_name(self):
        """测试会话创建时的名称处理"""
        # 清空会话数据
        sessions.clear()

        # 创建新会话
        session_id = get_or_create_session()

        # 检查初始状态
        assert session_id in sessions
        assert sessions[session_id]["name"] is None
        assert sessions[session_id]["chat_history"] == []

        print(f"✓ 会话 {session_id} 创建成功，初始名称为空")

    def test_session_name_update_on_first_message(self):
        """测试第一条消息时会话名称更新"""
        from app.api.v1.chat import generate_chat_stream, ChatRequest

        # 这里模拟第一条消息的处理逻辑
        sessions.clear()
        session_id = get_or_create_session()

        # 模拟第一条用户消息
        first_message = "请帮我分析销售数据的趋势"

        # 模拟聊天历史为空时的名称设置
        if len(sessions[session_id]["chat_history"]) == 0:
            session_name = clean_message_for_session_name(first_message)
            sessions[session_id]["name"] = session_name

        # 验证结果
        assert sessions[session_id]["name"] == "请帮我分析销售数据的趋势"
        print(f"✓ 会话名称已更新为: {sessions[session_id]['name']}")

    def test_multiple_sessions_with_different_names(self):
        """测试多个会话具有不同的名称"""
        sessions.clear()

        test_sessions = [
            ("请分析用户行为数据", "请分析用户行为数据"),
            ("如何优化机器学习模型？", "如何优化机器学习模型？"),
            ("数据可视化最佳实践", "数据可视化最佳实践"),
        ]

        created_sessions = []

        for message, expected_name in test_sessions:
            session_id = get_or_create_session()
            # 模拟第一条消息
            sessions[session_id]["name"] = clean_message_for_session_name(message)
            created_sessions.append((session_id, expected_name))

        # 验证每个会话都有正确的名称
        for session_id, expected_name in created_sessions:
            actual_name = sessions[session_id]["name"]
            assert actual_name == expected_name
            print(f"✓ 会话 {session_id[:8]}... 名称: {actual_name}")

    def test_session_list_response_format(self):
        """测试会话列表返回格式"""
        from app.api.v1.sessions import get_sessions

        sessions.clear()

        # 创建测试会话
        session_id = get_or_create_session()
        sessions[session_id]["name"] = "测试会话名称"

        # 异步运行测试
        async def run_test():
            session_list = await get_sessions()
            assert len(session_list) == 1

            session_info = session_list[0]
            assert session_info["id"] == session_id
            assert session_info["name"] == "测试会话名称"
            assert "created_at" in session_info
            assert "dataset_loaded" in session_info
            assert "chat_count" in session_info
            assert "analysis_count" in session_info

            print("✓ 会话列表格式正确")

        asyncio.run(run_test())


def run_interactive_test():
    """交互式测试"""
    print("=" * 60)
    print("交互式会话命名测试")
    print("输入消息查看生成的会话名称")
    print("输入 'quit' 退出")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n请输入用户消息: ").strip()
            if user_input.lower() == 'quit':
                break

            if user_input:
                session_name = clean_message_for_session_name(user_input)
                print(f"生成的会话名称: {session_name}")
                print(f"名称长度: {len(session_name)} 字符")
            else:
                print("请输入有效的消息内容")

        except KeyboardInterrupt:
            print("\n程序已退出")
            break


if __name__ == "__main__":
    # 运行所有测试
    test_instance = TestSessionNaming()

    print("开始测试会话命名功能...\n")

    try:
        test_instance.test_clean_message_for_session_name()
        test_instance.test_session_creation_with_name()
        test_instance.test_session_name_update_on_first_message()
        test_instance.test_multiple_sessions_with_different_names()
        test_instance.test_session_list_response_format()

        print("✅ 所有测试通过！")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 运行交互式测试
    print("\n" + "=" * 60)
    choice = input("是否运行交互式测试？(y/n): ").strip().lower()
    if choice in ['y', 'yes']:
        run_interactive_test()
