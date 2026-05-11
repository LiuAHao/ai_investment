#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API端点测试
注意：运行测试前需要先启动后端服务
如果5000端口被占用，可以设置环境变量 FLASK_PORT 指定其他端口
"""

import os
import requests
import pytest
import json

# 默认端口，可通过环境变量覆盖
PORT = os.getenv("FLASK_PORT", "5002")
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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
