#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自动化评测模块
提供规则评分、LLM评分、评测运行器
"""

from eval.metrics import calculate_final_score

__all__ = ["calculate_final_score"]
