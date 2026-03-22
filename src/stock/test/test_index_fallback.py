#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
指数行情 fallback 测试脚本
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

os.environ["AKSHARE_DISABLE_PROXY"] = "1"

from agent.data_agent import DataAgent


def main() -> None:
    agent = DataAgent()
    symbols = ["SH000001", "000001.SH"]
    for symbol in symbols:
        print(f"\n测试 {symbol}...")
        result = agent.analyze_daily_hist(symbol, start_date="20240101", end_date="20240131")
        print(result)


if __name__ == "__main__":
    main()
