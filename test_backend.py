#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
后端API测试脚本
"""

import requests
import json
import time

BASE_URL = "http://localhost:5000/api"


def test_health():
    """测试健康检查"""
    response = requests.get(f"{BASE_URL}/health")
    print(f"健康检查: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()


def test_register():
    """测试用户注册"""
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "test123456",
        "nickname": "测试用户",
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=data)
    print(f"注册: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()

    if response.status_code == 201:
        return response.json().get("token")
    return None


def test_login():
    """测试用户登录"""
    data = {"username": "testuser", "password": "test123456"}
    response = requests.post(f"{BASE_URL}/auth/login", json=data)
    print(f"登录: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()

    if response.status_code == 200:
        return response.json().get("token")
    return None


def test_agent_analyze(token):
    """测试Agent分析"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"symbol": "300750", "news_limit": 10}
    response = requests.post(f"{BASE_URL}/agent/analyze", json=data, headers=headers)
    print(f"启动分析: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()

    if response.status_code == 200:
        session_id = response.json().get("session_id")
        return session_id
    return None


def test_agent_status(token, session_id):
    """测试获取分析状态"""
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(20):
        response = requests.get(
            f"{BASE_URL}/agent/status/{session_id}", headers=headers
        )
        print(f"获取状态 (尝试 {i + 1}): {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()

        if result.get("status") in ["completed", "failed"]:
            break

        time.sleep(2)


def test_stock_analyze(token):
    """测试股票分析"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/stock/analyze?symbol=300750", headers=headers)
    print(f"股票分析: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()


def test_news_titles(token):
    """测试获取新闻标题"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/news/titles?limit=10", headers=headers)
    print(f"新闻标题: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()


def test_chat(token):
    """测试聊天"""
    headers = {"Authorization": f"Bearer {token}"}

    data = {"content": "你好，我想了解一下宁德时代", "session_id": "test_session"}
    response = requests.post(f"{BASE_URL}/chat/send", json=data, headers=headers)
    print(f"发送消息: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()

    response = requests.get(
        f"{BASE_URL}/chat/history?session_id=test_session", headers=headers
    )
    print(f"聊天历史: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print()


if __name__ == "__main__":
    print("=== 开始测试后端API ===\n")

    try:
        test_health()

        print("=== 认证测试 ===")
        token = test_login()
        if not token:
            token = test_register()

        if token:
            print(f"获取到Token: {token[:20]}...\n")

            print("=== Agent测试 ===")
            session_id = test_agent_analyze(token)
            if session_id:
                test_agent_status(token, session_id)

            print("\n=== 股票API测试 ===")
            test_stock_analyze(token)

            print("\n=== 新闻API测试 ===")
            test_news_titles(token)

            print("\n=== 聊天API测试 ===")
            test_chat(token)

    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到后端服务器")
        print("请确保后端服务已启动: python start_backend.py")
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")

    print("\n=== 测试完成 ===")
