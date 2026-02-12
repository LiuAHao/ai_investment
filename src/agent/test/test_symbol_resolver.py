#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SymbolResolver 测试
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.symbol_resolver import SymbolResolver


def test_resolve_company_name_to_symbol():
    resolver = SymbolResolver()
    result = resolver.resolve("请分析宁德时代财报")
    assert result.get("symbol") == "300750"
    assert result.get("method") in {"offline_master", "ambiguous_pick"}


def test_resolve_explicit_symbol_directly():
    resolver = SymbolResolver()
    result = resolver.resolve("分析 002378 后期走势")
    assert result.get("symbol") == "002378"
    assert result.get("method") == "explicit_code"


def test_resolve_unknown_name_returns_none():
    resolver = SymbolResolver()
    result = resolver.resolve("分析不存在的公司测试样本")
    assert result.get("symbol") is None
    assert result.get("method") == "not_found"
