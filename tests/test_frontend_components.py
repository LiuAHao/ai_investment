#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
前端组件测试
使用Playwright进行端到端测试
"""

import pytest
import asyncio
from playwright.async_api import async_playwright, expect

@pytest.fixture
def browser():
    """浏览器fixture"""
    async def _browser():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            yield browser
            await browser.close()
    return asyncio.get_event_loop().run_until_complete(_browser())

@pytest.fixture
def page(browser):
    """页面fixture"""
    async def _page():
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await context.close()
    return asyncio.get_event_loop().run_until_complete(_page())

class TestHomePage:
    """首页测试"""
    
    @pytest.mark.asyncio
    async def test_home_page_loads(self, page):
        """测试首页加载"""
        await page.goto('http://localhost:5173')
        
        # 检查页面标题
        title = await page.title()
        assert 'AI投资分析' in title or 'AI Investment' in title
        
        # 检查主要元素存在
        hero_text = await page.locator('h1').first.text_content()
        assert '你想研究什么' in hero_text or '研究' in hero_text
    
    @pytest.mark.asyncio
    async def test_navigation_buttons(self, page):
        """测试导航按钮"""
        await page.goto('http://localhost:5173')
        
        # 检查导航按钮存在
        research_btn = page.locator('button:has-text("研究")')
        await expect(research_btn).to_be_visible()
        
        history_btn = page.locator('button:has-text("历史")')
        await expect(history_btn).to_be_visible()
        
        settings_btn = page.locator('button:has-text("设置")')
        await expect(settings_btn).to_be_visible()

class TestResearchPage:
    """研究页面测试"""
    
    @pytest.mark.asyncio
    async def test_research_page_loads(self, page):
        """测试研究页面加载"""
        await page.goto('http://localhost:5173')
        
        # 点击研究按钮
        await page.click('button:has-text("研究")')
        
        # 检查页面跳转
        await page.wait_for_url('**/research')
        
        # 检查研究页面元素
        textarea = page.locator('textarea')
        await expect(textarea).to_be_visible()
        
        analyze_btn = page.locator('button:has-text("开始分析")')
        await expect(analyze_btn).to_be_visible()
    
    @pytest.mark.asyncio
    async def test_recommended_questions(self, page):
        """测试推荐问题"""
        await page.goto('http://localhost:5173')
        
        # 点击研究按钮
        await page.click('button:has-text("研究")')
        
        # 检查推荐问题存在
        recommended = page.locator('text=分析宁德时代未来三个月的风险')
        await expect(recommended).to_be_visible()

class TestFeedbackSystem:
    """反馈系统测试"""
    
    @pytest.mark.asyncio
    async def test_toast_notification(self, page):
        """测试Toast通知"""
        await page.goto('http://localhost:5173')
        
        # 模拟触发Toast通知的操作
        # 这里需要根据实际的触发条件来编写测试
        pass
    
    @pytest.mark.asyncio
    async def test_loading_state(self, page):
        """测试加载状态"""
        await page.goto('http://localhost:5173')
        
        # 模拟触发加载状态的操作
        # 这里需要根据实际的触发条件来编写测试
        pass

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
