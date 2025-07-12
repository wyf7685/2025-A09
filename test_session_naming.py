"""
测试会话名称自动设置功能
"""

import re
from app.api.v1.chat import clean_message_for_session_name


def test_clean_message_for_session_name():
    """测试会话名称清理函数"""
    
    # 测试用例
    test_cases = [
        # 正常的中文消息
        ("分析数据的基本统计信息", "分析数据的基本统计信息"),
        
        # 英文消息
        ("Analyze the basic statistics of the data", "Analyze the basic statistics of the data"),
        
        # 混合中英文
        ("分析数据的基本统计信息 Analyze data", "分析数据的基本统计信息 Analyze data"),
        
        # 包含特殊字符的消息
        ("分析数据的基本统计信息！@#$%^&*()", "分析数据的基本统计信息！"),
        
        # 超长消息
        ("这是一个非常长的消息，用来测试会话名称的截断功能，确保它能够正确地处理长文本", "这是一个非常长的消息，用来测试会话名称的截断功能..."),
        
        # 包含换行符的消息
        ("分析数据\n的基本统计信息", "分析数据 的基本统计信息"),
        
        # 空消息
        ("", "未命名对话"),
        
        # 只有空白字符的消息
        ("   \n\t  ", "未命名对话"),
        
        # 包含标点符号的长消息
        ("分析数据的基本统计信息，包括均值、方差、最大值、最小值等。", "分析数据的基本统计信息，包括均值、方差、最大值、最小值等。"),
    ]
    
    print("测试会话名称清理功能:")
    print("=" * 50)
    
    for i, (input_msg, expected) in enumerate(test_cases, 1):
        result = clean_message_for_session_name(input_msg)
        status = "✓" if result == expected else "✗"
        print(f"{i}. {status} 输入: '{input_msg}'")
        print(f"   输出: '{result}'")
        print(f"   期望: '{expected}'")
        print()
    
    print("测试完成！")


if __name__ == "__main__":
    test_clean_message_for_session_name() 