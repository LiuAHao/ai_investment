#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主控 Agent 测试程序
"""

import os
import sys
from typing import Optional

# 确保可从项目 src 目录导入
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from agent.master_agent import MasterAgent


def main():
    agent = MasterAgent()

    print("=== LLM 决策链路 ===")
    query = "分析贵州茅台的近期表现，并给出风险提示。"
    llm_result: Optional[str] = None
    try:
        llm_result = agent.run_query(query)
    except Exception as exc:
        print("LLM 调用失败:", str(exc))

    if llm_result:
        print(llm_result)


if __name__ == "__main__":
    main()
