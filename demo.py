#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web应用演示脚本
用于展示系统主要功能和生成演示数据
"""

import requests
import json
import pandas as pd
import time
import os
from datetime import datetime, timedelta
import random

BASE_URL = "http://localhost:5000"

def create_demo_data():
    """创建演示数据文件"""
    print("📊 创建演示数据...")
    
    # 销售数据
    dates = [(datetime.now() - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(30, 0, -1)]
    sales_data = {
        'date': dates,
        'product': ['产品A', '产品B', '产品C'] * 10,
        'sales_amount': [random.randint(1000, 5000) for _ in range(30)],
        'quantity': [random.randint(10, 100) for _ in range(30)],
        'region': ['北京', '上海', '广州', '深圳', '杭州'] * 6,
        'customer_type': ['企业客户', '个人客户'] * 15
    }
    
    sales_df = pd.DataFrame(sales_data)
    sales_df.to_csv('demo_sales_data.csv', index=False, encoding='utf-8')
    print("✅ 销售数据已生成: demo_sales_data.csv")
    
    # 用户行为数据
    user_data = {
        'user_id': [f'user_{i:04d}' for i in range(1, 101)],
        'age': [random.randint(18, 65) for _ in range(100)],
        'gender': ['男', '女'] * 50,
        'city': ['北京', '上海', '广州', '深圳', '杭州', '成都', '西安', '武汉'] * 12 + ['北京'] * 4,
        'visit_count': [random.randint(1, 50) for _ in range(100)],
        'purchase_amount': [random.randint(0, 10000) for _ in range(100)],
        'last_login': [(datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d') for _ in range(100)]
    }
    
    user_df = pd.DataFrame(user_data)
    user_df.to_csv('demo_user_data.csv', index=False, encoding='utf-8')
    print("✅ 用户数据已生成: demo_user_data.csv")
    
    return ['demo_sales_data.csv', 'demo_user_data.csv']

def demo_file_upload(filename):
    """演示文件上传功能"""
    print(f"📤 演示文件上传: {filename}")
    
    try:
        with open(filename, 'rb') as f:
            files = {'file': (filename, f, 'text/csv')}
            response = requests.post(f"{BASE_URL}/api/upload", files=files, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 文件上传成功!")
            print(f"   文件名: {result['filename']}")
            print(f"   数据形状: {result['shape']}")
            print(f"   列名: {', '.join(result['columns'])}")
            return result
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 文件上传异常: {e}")
        return None

def demo_chat_analysis():
    """演示对话分析功能"""
    print("💬 演示对话分析功能...")
    
    questions = [
        "你好，请介绍一下你的数据分析能力",
        "请帮我分析一下销售数据的整体趋势",
        "哪个地区的销售表现最好？",
        "用户的年龄分布如何？",
        "给我一些提升销售的建议"
    ]
    
    session_id = f"demo_session_{int(time.time())}"
    
    for i, question in enumerate(questions, 1):
        print(f"\n🤔 问题 {i}: {question}")
        
        try:
            chat_request = {
                "message": question,
                "session_id": session_id
            }
            
            response = requests.post(f"{BASE_URL}/api/chat", 
                                   json=chat_request, 
                                   timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                print(f"🤖 回答: {result['response'][:200]}...")
                time.sleep(2)  # 避免请求过快
            else:
                print(f"❌ 对话请求失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 对话异常: {e}")

def demo_auto_analysis():
    """演示自动分析功能"""
    print("🔍 演示自动分析功能...")
    
    try:
        analysis_request = {
            "dataset_path": "demo_sales_data.csv",
            "analysis_type": "comprehensive"
        }
        
        response = requests.post(f"{BASE_URL}/api/analysis/general", 
                               json=analysis_request, 
                               timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 自动分析完成!")
            print(f"   报告ID: {result['report_id']}")
            print(f"   分析摘要: {result['summary'][:150]}...")
            return result
        else:
            print(f"❌ 自动分析失败: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 自动分析异常: {e}")
        return None

def demo_session_management():
    """演示会话管理功能"""
    print("📋 演示会话管理功能...")
    
    # 创建新会话
    try:
        session_data = {
            "name": f"演示会话 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
        
        response = requests.post(f"{BASE_URL}/api/sessions", 
                               json=session_data, 
                               timeout=5)
        
        if response.status_code == 201:
            session = response.json()
            print(f"✅ 创建会话成功: {session['name']}")
            
            # 获取会话列表
            response = requests.get(f"{BASE_URL}/api/sessions", timeout=5)
            if response.status_code == 200:
                sessions = response.json()
                print(f"📋 会话列表 (共{len(sessions)}个):")
                for sess in sessions[:3]:  # 只显示前3个
                    print(f"   - {sess['name']} (ID: {sess['id']})")
                return session
            
        else:
            print(f"❌ 会话创建失败: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 会话管理异常: {e}")
        return None

def demo_model_management():
    """演示模型管理功能"""
    print("🎯 演示模型管理功能...")
    
    try:
        # 获取模型列表
        response = requests.get(f"{BASE_URL}/api/models", timeout=5)
        
        if response.status_code == 200:
            models = response.json()
            print(f"📋 模型列表 (共{len(models)}个):")
            for model in models[:3]:  # 只显示前3个
                print(f"   - {model['name']} (类型: {model['type']}, 状态: {model['status']})")
            
            # 尝试创建新模型
            new_model = {
                "name": "演示分类模型",
                "type": "classification", 
                "description": "用于演示的分类模型",
                "config": {"algorithm": "random_forest", "n_estimators": 100}
            }
            
            response = requests.post(f"{BASE_URL}/api/models", 
                                   json=new_model, 
                                   timeout=10)
            
            if response.status_code == 201:
                result = response.json()
                print(f"✅ 创建模型成功: {result['name']}")
            else:
                print(f"⚠️  模型创建跳过 (可能已存在)")
                
        else:
            print(f"❌ 获取模型列表失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 模型管理异常: {e}")

def cleanup_demo_files():
    """清理演示文件"""
    print("🧹 清理演示文件...")
    
    demo_files = ['demo_sales_data.csv', 'demo_user_data.csv']
    
    for filename in demo_files:
        if os.path.exists(filename):
            os.remove(filename)
            print(f"✅ 已删除: {filename}")

def main():
    """运行完整演示"""
    print("🎬 数据分析Web应用功能演示")
    print("=" * 60)
    
    # 检查后端服务
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code != 200:
            print("❌ 后端服务未启动，请先运行 python web_app.py")
            return False
    except:
        print("❌ 无法连接到后端服务，请确保服务正在运行")
        return False
    
    print("✅ 后端服务连接正常")
    print()
    
    try:
        # 1. 创建演示数据
        demo_files = create_demo_data()
        print()
        
        # 2. 演示文件上传
        for filename in demo_files:
            demo_file_upload(filename)
        print()
        
        # 3. 演示会话管理
        session = demo_session_management()
        print()
        
        # 4. 演示对话分析
        demo_chat_analysis()
        print()
        
        # 5. 演示自动分析
        demo_auto_analysis()
        print()
        
        # 6. 演示模型管理
        demo_model_management()
        print()
        
        print("🎉 所有功能演示完成!")
        print()
        print("📍 你可以通过以下方式继续探索:")
        print("   - 前端界面: http://localhost:5173")
        print("   - API文档: 查看 web_app.py 中的接口定义")
        print("   - 测试脚本: python test_web_app.py")
        
    except KeyboardInterrupt:
        print("\n⚠️  演示被用户中断")
    except Exception as e:
        print(f"\n❌ 演示过程出错: {e}")
    finally:
        # 清理演示文件
        cleanup_demo_files()
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
