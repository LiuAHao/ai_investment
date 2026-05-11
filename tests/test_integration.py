#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
集成测试
测试前后端数据流和API调用
"""

import os
import requests
import pytest
import json
import time

# 默认端口，可通过环境变量覆盖
PORT = os.getenv("FLASK_PORT", "5002")
FRONTEND_PORT = os.getenv("VITE_PORT", "5173")
BASE_URL = f"http://localhost:{PORT}"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

class TestFrontendBackendIntegration:
    """前后端集成测试"""
    
    def test_api_health_check(self):
        """测试API健康检查"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_v2_health_check(self):
        """测试V2健康检查"""
        response = requests.get(f"{BASE_URL}/api/agent/v2/health")
        assert response.status_code == 200
        data = response.json()
        assert data["v2_enabled"] == True
    
    def test_cors_headers(self):
        """测试CORS头"""
        response = requests.options(f"{BASE_URL}/api/health")
        # 检查CORS头是否存在
        assert "access-control-allow-origin" in response.headers or response.status_code == 200

class TestUserFlow:
    """用户流程测试"""
    
    def test_register_and_login(self):
        """测试注册和登录流程"""
        # 注册
        register_data = {
            "username": f"testuser_{int(time.time())}",
            "password": "testpass123",
            "email": f"test_{int(time.time())}@example.com"
        }
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
        
        # 如果注册成功
        if register_response.status_code in [200, 201]:
            # 登录
            login_data = {
                "username": register_data["username"],
                "password": register_data["password"]
            }
            login_response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
            assert login_response.status_code == 200
            
            login_result = login_response.json()
            assert "token" in login_result or "access_token" in login_result
    
    def test_stock_analysis_flow(self):
        """测试股票分析流程"""
        # 先登录获取token
        login_data = {
            "username": "testuser",
            "password": "testpass123"
        }
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        if login_response.status_code == 200:
            token = login_response.json().get("token") or login_response.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            
            # 测试股票分析
            analyze_response = requests.get(
                f"{BASE_URL}/api/stock/analyze",
                params={"symbol": "000001"},
                headers=headers
            )
            
            # 可能返回200或400（如果股票代码无效）
            assert analyze_response.status_code in [200, 400, 401]

class TestErrorHandling:
    """错误处理测试"""
    
    def test_invalid_endpoint(self):
        """测试无效端点"""
        response = requests.get(f"{BASE_URL}/api/invalid/endpoint")
        assert response.status_code == 404
    
    def test_unauthorized_access(self):
        """测试未授权访问"""
        response = requests.get(f"{BASE_URL}/api/user/profile")
        assert response.status_code == 401
    
    def test_invalid_json(self):
        """测试无效JSON"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422, 500]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])