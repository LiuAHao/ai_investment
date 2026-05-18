#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
认证入口 smoke 测试
要求本地后端已启动。
"""

import time

import pytest
import requests


pytestmark = pytest.mark.smoke


def _unique_user() -> dict:
    timestamp = int(time.time() * 1000)
    return {
        "username": f"smoke_user_{timestamp}",
        "password": "testpass123",
        "email": f"smoke_user_{timestamp}@example.com",
    }


def _register(base_url: str, user: dict) -> requests.Response:
    return requests.post(f"{base_url}/api/auth/register", json=user, timeout=10)


def test_register_returns_201_and_token(base_url):
    """注册成功必须返回 token 和用户信息"""
    user = _unique_user()

    response = _register(base_url, user)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["message"] == "注册成功"
    assert data["token"]
    assert data["user"]["username"] == user["username"]
    assert data["user"]["email"] == user["email"]


def test_login_returns_200_and_token_after_register(base_url):
    """注册后的用户应能立即登录"""
    user = _unique_user()
    register_response = _register(base_url, user)
    assert register_response.status_code == 201, register_response.text

    login_response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": user["username"], "password": user["password"]},
        timeout=10,
    )

    assert login_response.status_code == 200, login_response.text
    data = login_response.json()
    assert data["message"] == "登录成功"
    assert data["token"]
    assert data["user"]["username"] == user["username"]


def test_profile_requires_auth(base_url):
    """未登录访问 profile 必须返回 401"""
    response = requests.get(f"{base_url}/api/user/profile", timeout=10)

    assert response.status_code == 401, response.text
    assert response.json()["error"] == "未授权"


def test_profile_returns_user_with_valid_token(base_url):
    """有效 token 应能读取用户信息"""
    user = _unique_user()
    register_response = _register(base_url, user)
    assert register_response.status_code == 201, register_response.text
    token = register_response.json()["token"]

    profile_response = requests.get(
        f"{base_url}/api/user/profile",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert profile_response.status_code == 200, profile_response.text
    data = profile_response.json()
    assert data["username"] == user["username"]
    assert data["email"] == user["email"]
    assert data["user_tier"]
    assert "quota" in data
