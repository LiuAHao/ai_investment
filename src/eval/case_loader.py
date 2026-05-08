#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评测用例加载器
从 JSONL 文件加载评测用例
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DATASETS_DIR = Path(__file__).parent / "datasets"


class ExpectedBehavior(BaseModel):
    """期望行为"""
    must_include: List[str] = Field(default_factory=list)
    must_not_include: List[str] = Field(default_factory=list)
    expected_tools: List[str] = Field(default_factory=list)
    forbidden_tools: List[str] = Field(default_factory=list)
    expected_asset_types: List[str] = Field(default_factory=list)


class EvalCase(BaseModel):
    """评测用例"""
    case_id: str
    category: str
    query: str
    chat_history: List[Dict[str, str]] = Field(default_factory=list)
    user_profile: Dict[str, Any] = Field(default_factory=dict)
    expected_behavior: ExpectedBehavior = Field(default_factory=ExpectedBehavior)
    reference_answer: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


def load_cases(dataset_name: str, limit: Optional[int] = None) -> List[EvalCase]:
    """
    加载评测用例
    
    Args:
        dataset_name: 数据集名称（不含扩展名）
        limit: 最大加载数量
        
    Returns:
        评测用例列表
    """
    filepath = DATASETS_DIR / f"{dataset_name}.jsonl"
    
    if not filepath.exists():
        logger.warning("数据集文件不存在: %s", filepath)
        return []
    
    cases = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    case = EvalCase(**data)
                    cases.append(case)
                except Exception as e:
                    logger.warning("解析用例失败: %s, error: %s", line[:50], e)
                
                if limit and len(cases) >= limit:
                    break
    except Exception as e:
        logger.error("加载数据集失败: %s, error: %s", filepath, e)
    
    logger.info("加载评测用例: %s, %d 条", dataset_name, len(cases))
    return cases


def load_all_cases(limit_per_dataset: Optional[int] = None) -> List[EvalCase]:
    """加载所有数据集"""
    all_cases = []
    
    for filepath in DATASETS_DIR.glob("*.jsonl"):
        dataset_name = filepath.stem
        cases = load_cases(dataset_name, limit_per_dataset)
        all_cases.extend(cases)
    
    return all_cases


def get_available_datasets() -> List[str]:
    """获取可用数据集列表"""
    datasets = []
    for filepath in DATASETS_DIR.glob("*.jsonl"):
        datasets.append(filepath.stem)
    return sorted(datasets)
