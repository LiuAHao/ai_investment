#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 Agent 模块
基于 LangGraph 的动态编排系统
"""

from agent.v2.state import InvestmentState
from agent.v2.graph import build_graph

__all__ = ["InvestmentState", "build_graph"]
