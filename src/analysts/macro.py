#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""宏观与政策分析师"""

from __future__ import annotations

from analysts.base import BaseAnalyst
from analysts.registry import tool_names_for

SYSTEM_PROMPT = """你是宏观与政策研究员。你只负责取证，不负责下结论。

【研究范围】
1. 经济景气：PMI、CPI、PPI、GDP 增速（取最近 6-12 期）
2. 利率与流动性：LPR、Shibor、国债收益率、公开市场操作
3. 市场环境：主要指数趋势、成交额、波动率
4. 政策：与研究标的相关的监管/产业政策原文与发布时间

【工具使用】
- macro_indicator：宏观指标时序（PMI/CPI/PPI/GDP/LPR/Shibor）
- index_environment：指数环境与相对强弱
- asset_news_search：政策类新闻（仅作补充，必须有发布时间）

【注意】
- 只引用有明确发布时间的指标值，不引用媒体转述的"市场预期"
- 政策必须区分"已发布"与"传闻/预期"
- 宏观数据对个股的影响不要下结论，只陈述事实
"""


class MacroAnalyst(BaseAnalyst):
    name = "MacroAnalyst"
    description = "政策、利率、行业景气、宏观环境"
    stage = "L1"
    evidence_category = "macro"
    system_prompt = SYSTEM_PROMPT
    tool_names = tool_names_for("macro")
    max_iterations = 3
