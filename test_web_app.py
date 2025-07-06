#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web应用测试脚本
用于测试前后端API连接和基本功能
"""

import requests
import json
import time
import os

# 配置
BASE_URL = "http://localhost:5000"
FRONTEND_URL = "http://localhost:5173"

def test_backend_health():
    """测试后端健康检查"""
    print("🔍 测试后端健康检查...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ 后端服务运行正常")
            return True
        else:
            print(f"❌ 后端健康检查失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 无法连接到后端服务: {e}")
        return False

def test_frontend_access():
    """测试前端访问"""
    print("🔍 测试前端访问...")
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print("✅ 前端服务运行正常")
            return True
        else:
            print(f"❌ 前端访问失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 无法连接到前端服务: {e}")
        return False

def test_session_management():
    """测试会话管理"""
    print("🔍 测试会话管理...")
    try:
        # 创建新会话
        response = requests.post(f"{BASE_URL}/api/sessions", 
                               json={"name": "测试会话"}, 
                               timeout=5)
        if response.status_code == 201:
            session_data = response.json()
            print(f"✅ 创建会话成功: {session_data['name']}")
            
            # 获取会话列表
            response = requests.get(f"{BASE_URL}/api/sessions", timeout=5)
            if response.status_code == 200:
                sessions = response.json()
                print(f"✅ 获取会话列表成功，共 {len(sessions)} 个会话")
                return True
            else:
                print(f"❌ 获取会话列表失败: {response.status_code}")
                return False
        else:
            print(f"❌ 创建会话失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 会话管理测试失败: {e}")
        return False

def test_file_upload():
    """测试文件上传"""
    print("🔍 测试文件上传...")
    
    # 创建测试CSV文件
    test_data = """name,age,city
张三,25,北京
李四,30,上海
王五,35,广州"""
    
    test_file_path = "test_upload.csv"
    try:
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_data)
        
        # 上传文件
        with open(test_file_path, 'rb') as f:
            files = {'file': ('test_upload.csv', f, 'text/csv')}
            response = requests.post(f"{BASE_URL}/api/upload", 
                                   files=files, 
                                   timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 文件上传成功: {result['filename']}")
            print(f"   数据形状: {result['shape']}")
            return True
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            if response.text:
                print(f"   错误信息: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 文件上传测试失败: {e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

def test_chat_analysis():
    """测试对话分析"""
    print("🔍 测试对话分析...")
    try:
        chat_request = {
            "message": "你好，请介绍一下你的分析能力",
            "session_id": "test-session"
        }
        
        response = requests.post(f"{BASE_URL}/api/chat", 
                               json=chat_request, 
                               timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 对话分析成功")
            print(f"   响应: {result['response'][:100]}...")
            return True
        else:
            print(f"❌ 对话分析失败: {response.status_code}")
            if response.text:
                print(f"   错误信息: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 对话分析测试失败: {e}")
        return False

def test_cors():
    """测试CORS配置"""
    print("🔍 测试CORS配置...")
    try:
        headers = {
            'Origin': FRONTEND_URL,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type'
        }
        
        response = requests.options(f"{BASE_URL}/api/health", 
                                  headers=headers, 
                                  timeout=5)
        
        if response.status_code in [200, 204]:
            cors_headers = response.headers
            if 'Access-Control-Allow-Origin' in cors_headers:
                print("✅ CORS配置正确")
                return True
            else:
                print("❌ CORS头缺失")
                return False
        else:
            print(f"❌ CORS预检请求失败: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ CORS测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("🚀 开始Web应用测试")
    print("=" * 50)
    
    tests = [
        ("后端健康检查", test_backend_health),
        ("前端访问", test_frontend_access),
        ("CORS配置", test_cors),
        ("会话管理", test_session_management),
        ("文件上传", test_file_upload),
        ("对话分析", test_chat_analysis),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试 '{test_name}' 异常: {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # 间隔1秒
    
    # 输出测试总结
    print("\n" + "=" * 50)
    print("📊 测试结果总结")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20} : {status}")
    
    print("-" * 50)
    print(f"总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！Web应用运行正常")
        return True
    else:
        print("⚠️  部分测试失败，请检查相关服务")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
