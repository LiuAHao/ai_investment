#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
前端组件 smoke 测试
要求本地前端开发服务器已启动。
"""

import os

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.smoke

FRONTEND_PORT = os.getenv("VITE_PORT", "5173")
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"


class TestHomePage:
    """首页测试"""

    def test_home_page_loads(self, page):
        """首页应能加载并展示产品标题"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        expect(page.locator("body")).to_be_visible()
        expect(page.locator("text=AI 投资研究").first).to_be_visible()

    def test_navigation_buttons(self, page):
        """首页应展示主要导航入口"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        expect(page.get_by_role("button", name="研究", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="历史")).to_be_visible()
        expect(page.get_by_role("button", name="设置")).to_be_visible()


class TestResearchPage:
    """研究页面测试"""

    def test_research_page_loads(self, page):
        """点击研究入口后应展示研究输入框"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="研究", exact=True).click()

        expect(page.get_by_placeholder("输入你想研究的投资问题, 例如: 分析宁德时代未来三个月的风险")).to_be_visible()
        expect(page.get_by_role("button", name="开始分析")).to_be_visible()

    def test_recommended_questions(self, page):
        """研究页应展示推荐问题"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="研究", exact=True).click()

        expect(page.get_by_text("分析宁德时代未来三个月的风险")).to_be_visible()


class TestAuthPage:
    """认证页面测试"""

    def test_register_form_contains_required_fields(self, page):
        """注册页应展示用户名、邮箱和密码字段"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="注册 / 登录").click()
        page.get_by_role("button", name="立即注册").click()

        expect(page.get_by_placeholder("请输入用户名")).to_be_visible()
        expect(page.get_by_placeholder("请输入邮箱")).to_be_visible()
        expect(page.get_by_placeholder("请输入密码")).to_be_visible()

    def test_login_form_contains_required_fields(self, page):
        """登录页应展示用户名和密码字段"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="注册 / 登录").click()

        expect(page.get_by_placeholder("请输入用户名")).to_be_visible()
        expect(page.get_by_placeholder("请输入密码")).to_be_visible()
