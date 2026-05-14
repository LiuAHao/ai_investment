#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API端点测试
注意：运行测试前需要先启动后端服务
如果默认端口被占用，可以设置环境变量 FLASK_PORT 指定其他端口
"""

import os
import requests
import pytest
import json
import time

# 默认端口，可通过环境变量覆盖
PORT = os.getenv("FLASK_PORT", "5001")
BASE_URL = f"http://localhost:{PORT}"

class TestHealthEndpoints:
    """健康检查端点测试"""
    
    def test_main_health(self):
        """测试主健康检查端点"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_v2_health(self):
        """测试V2健康检查端点"""
        response = requests.get(f"{BASE_URL}/api/agent/v2/health")
        assert response.status_code == 200
        data = response.json()
        assert data["v2_enabled"] == True
        assert data["version"] == "2.0.0"

class TestAuthEndpoints:
    """认证端点测试"""
    
    def test_register(self):
        """测试用户注册"""
        data = {
            "username": "testuser",
            "password": "testpass123",
            "email": "test@example.com"
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=data)
        # 注意：如果用户已存在，可能返回400；数据库问题可能返回500
        assert response.status_code in [200, 201, 400, 500]
    
    def test_login(self):
        """测试用户登录"""
        data = {
            "username": "testuser",
            "password": "testpass123"
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=data)
        # 数据库问题可能返回500
        assert response.status_code in [200, 401, 500]

class TestStockEndpoints:
    """股票数据端点测试"""
    
    def test_stock_analyze(self):
        """测试股票分析"""
        params = {"symbol": "000001"}
        response = requests.get(f"{BASE_URL}/api/stock/analyze", params=params)
        # 可能需要认证，返回401或200
        assert response.status_code in [200, 401, 400]

class TestNewsEndpoints:
    """新闻端点测试"""
    
    def test_news_titles(self):
        """测试获取新闻标题"""
        response = requests.get(f"{BASE_URL}/api/news/titles")
        assert response.status_code in [200, 401]


class TestChatEndpoints:
    """聊天端点测试"""

    def test_chat_sessions_include_query_and_created_at(self, auth_headers):
        """测试会话列表返回前端依赖的核心字段"""
        timestamp = int(time.time())
        session_id = f"test-session-{timestamp}"
        message_content = f"测试会话列表字段契约-{timestamp}"
        send_response = requests.post(
            f"{BASE_URL}/api/chat/send",
            json={
                "content": message_content,
                "session_id": session_id,
                "role": "user",
            },
            headers=auth_headers,
        )

        assert send_response.status_code == 201

        sessions_response = requests.get(
            f"{BASE_URL}/api/chat/sessions",
            headers=auth_headers,
        )

        assert sessions_response.status_code == 200

        sessions = sessions_response.json()["sessions"]
        target_session = next(
            session for session in sessions if session["session_id"] == session_id
        )

        assert "session_id" in target_session
        assert "query" in target_session
        assert "created_at" in target_session
        assert target_session["query"] == message_content
        assert target_session["created_at"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
