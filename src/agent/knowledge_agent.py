#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库 Agent：封装 RAG 检索能力
"""

from typing import Any, Dict, Optional

from rag.knowledge_tool import query_investment_knowledge


class KnowledgeAgent:
    """知识库 Agent"""

    def query(self, query: str, top_k: Optional[int] = 5) -> Dict[str, Any]:
        """
        执行投资知识库检索

        Args:
            query: 用户问题
            top_k: 返回条数

        Returns:
            知识库检索结果
        """
        return query_investment_knowledge(query=query, top_k=top_k)
