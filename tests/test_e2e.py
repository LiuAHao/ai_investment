#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
端到端测试
测试完整的用户流程
"""

import os

import pytest


FRONTEND_PORT = os.getenv("VITE_PORT", "5173")
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

class TestUserJourney:
    """用户旅程测试"""
    
    def test_home_page_loads(self, page):
        """测试首页加载"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state('networkidle')
        
        # 检查页面标题
        title = page.title()
        assert title is not None
        
        # 检查首页内容
        heading = page.locator('h1')
        heading.wait_for(state='visible', timeout=5000)
    
    def test_navigate_to_research(self, page):
        """测试导航到研究页面"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state('networkidle')
        
        # 点击"开始研究"按钮
        research_btn = page.locator('button:has-text("开始研究")')
        research_btn.first.click()
        
        # 等待页面跳转
        page.wait_for_timeout(500)
        
        # 检查是否显示研究页面的textarea
        textarea = page.locator('textarea')
        textarea.wait_for(state='visible', timeout=5000)
    
    def test_research_input(self, page):
        """测试研究输入"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state('networkidle')
        
        # 导航到研究页面
        research_btn = page.locator('button:has-text("开始研究")')
        research_btn.first.click()
        page.wait_for_timeout(500)
        
        # 输入研究问题
        textarea = page.locator('textarea')
        textarea.fill('分析宁德时代未来三个月的风险')
        
        # 验证输入
        value = textarea.input_value()
        assert '宁德时代' in value

class TestNavigation:
    """导航测试"""
    
    def test_nav_buttons_exist(self, page):
        """测试导航按钮存在"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state('networkidle')
        
        # 检查导航按钮
        buttons = page.locator('button')
        count = buttons.count()
        assert count > 0
    
    def test_login_button_exists(self, page):
        """测试登录按钮存在"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state('networkidle')
        
        # 检查认证入口
        login_btn = page.get_by_role("button", name="注册 / 登录")
        login_btn.wait_for(state='visible', timeout=5000)

class TestFeedbackSystemE2E:
    """反馈系统端到端测试"""
    
    def test_page_responsive(self, page):
        """测试页面响应性"""
        page.goto(FRONTEND_URL)
        page.wait_for_load_state('networkidle')
        
        # 检查页面是否响应
        page.wait_for_timeout(500)
        
        # 页面应该仍然可用
        body = page.locator('body')
        body.wait_for(state='visible', timeout=5000)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
