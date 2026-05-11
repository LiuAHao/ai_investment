#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pytest配置文件
"""

import pytest
import requests
import time

BASE_URL = "http://localhost:5000"
FRONTEND_URL = "http://localhost:5173"

@pytest.fixture(scope="session")
def base_url():
    """基础URL fixture"""
    return BASE_URL

@pytest.fixture(scope="session")
def frontend_url():
    """前端URL fixture"""
    return FRONTEND_URL

@pytest.fixture(scope="session")
def test_user():
    """测试用户fixture"""
    timestamp = int(time.time())
    return {
        "username": f"testuser_{timestamp}",
        "password": "testpass123",
        "email": f"test_{timestamp}@example.com"
    }

@pytest.fixture(scope="session")
def auth_token(test_user):
    """认证token fixture"""
    # 先注册
    register_response = requests.post(f"{BASE_URL}/api/auth/register", json=test_user)
    
    # 再登录
    login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": test_user["username"],
        "password": test_user["password"]
    })
    
    if login_response.status_code == 200:
        return login_response.json().get("token") or login_response.json().get("access_token")
    
    return None

@pytest.fixture
def auth_headers(auth_token):
    """认证头fixture"""
    if auth_token:
        return {"Authorization": f"Bearer {auth_token}"}
    return {}
