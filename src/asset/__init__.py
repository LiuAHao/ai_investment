#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
资产主数据管理器
加载和查询资产主数据
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.state import Asset, AssetType

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"


class AssetMasterData:
    """资产主数据管理器"""

    def __init__(self):
        self._assets: Dict[str, Asset] = {}
        self._by_symbol: Dict[str, List[Asset]] = {}
        self._by_name: Dict[str, List[Asset]] = {}
        self._by_alias: Dict[str, List[Asset]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """确保数据已加载"""
        if not self._loaded:
            self._load_all()
            self._loaded = True

    def _load_all(self) -> None:
        """加载所有主数据文件"""
        files = {
            AssetType.CN_STOCK: "cn_stock_master.jsonl",
            AssetType.US_STOCK: "us_stock_master.jsonl",
            AssetType.ETF: "etf_master.jsonl",
            AssetType.FUND: "fund_master.jsonl",
            AssetType.INDEX: "index_master.jsonl",
            AssetType.MACRO: "macro_master.jsonl",
            AssetType.INDUSTRY: "industry_master.jsonl",
        }

        for asset_type, filename in files.items():
            filepath = DATA_DIR / filename
            if filepath.exists():
                self._load_file(filepath, asset_type)

        logger.info("加载资产主数据: %d 条", len(self._assets))

    def _load_file(self, filepath: Path, asset_type: AssetType) -> None:
        """加载单个主数据文件"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        asset = Asset(
                            asset_id=data.get("asset_id", ""),
                            asset_type=asset_type,
                            symbol=data.get("symbol"),
                            name=data.get("name"),
                            market=data.get("market"),
                            exchange=data.get("exchange"),
                            currency=data.get("currency"),
                            aliases=data.get("aliases", []),
                            metadata={k: v for k, v in data.items() 
                                     if k not in ("asset_id", "asset_type", "symbol", "name", 
                                                  "market", "exchange", "currency", "aliases")},
                        )
                        self._index_asset(asset)
                    except json.JSONDecodeError as e:
                        logger.warning("解析行失败: %s, error: %s", line[:50], e)
        except Exception as e:
            logger.warning("加载文件失败: %s, error: %s", filepath, e)

    def _index_asset(self, asset: Asset) -> None:
        """索引资产"""
        self._assets[asset.asset_id] = asset

        if asset.symbol:
            if asset.symbol not in self._by_symbol:
                self._by_symbol[asset.symbol] = []
            self._by_symbol[asset.symbol].append(asset)

        if asset.name:
            key = asset.name.lower()
            if key not in self._by_name:
                self._by_name[key] = []
            self._by_name[key].append(asset)

        for alias in asset.aliases:
            key = alias.lower()
            if key not in self._by_alias:
                self._by_alias[key] = []
            self._by_alias[key].append(asset)

    def find_by_symbol(self, symbol: str) -> List[Asset]:
        """根据代码查找资产"""
        self._ensure_loaded()
        return self._by_symbol.get(symbol, [])

    def find_by_name(self, name: str) -> List[Asset]:
        """根据名称查找资产"""
        self._ensure_loaded()
        return self._by_name.get(name.lower(), [])

    def find_by_alias(self, alias: str) -> List[Asset]:
        """根据别名查找资产"""
        self._ensure_loaded()
        return self._by_alias.get(alias.lower(), [])

    def find_by_asset_id(self, asset_id: str) -> Optional[Asset]:
        """根据 asset_id 查找资产"""
        self._ensure_loaded()
        return self._assets.get(asset_id)

    def search(self, query: str, limit: int = 10) -> List[Asset]:
        """搜索资产"""
        self._ensure_loaded()
        results = []
        query_lower = query.lower()
        tokens = self._extract_search_tokens(query)

        for asset in self._assets.values():
            score = 0.0
            candidates = [query_lower] + tokens

            if asset.name and asset.name.lower() in query_lower:
                score = max(score, 0.95)
            for alias in asset.aliases:
                if alias.lower() in query_lower:
                    score = max(score, 0.9)

            for token in candidates:
                if not token:
                    continue
                if asset.symbol and token.upper() == asset.symbol.upper():
                    score = max(score, 1.0)
                elif asset.symbol and token in asset.symbol.lower():
                    score = max(score, 0.85)
                elif asset.name and token in asset.name.lower():
                    score = max(score, 0.9)
                elif any(token in alias.lower() for alias in asset.aliases):
                    score = max(score, 0.8)

            if score > 0:
                updated = asset.model_copy(update={"confidence": score})
                results.append((score, updated))

        results.sort(key=lambda x: x[0], reverse=True)
        return [asset for _, asset in results[:limit]]

    @staticmethod
    def _extract_search_tokens(query: str) -> List[str]:
        """从自然语言查询中提取资产搜索词"""
        text = (query or "").strip()
        stopwords = {
            "分析",
            "看看",
            "一下",
            "风险",
            "走势",
            "后市",
            "未来",
            "近期",
            "基金",
            "股票",
            "港股",
            "美股",
            "如何",
            "怎么",
            "怎么看",
            "适合",
        }
        tokens: List[str] = []

        for item in re.findall(r"[A-Za-z]{1,10}|\d{5,6}|[\u4e00-\u9fa5A-Za-z0-9]{2,16}", text):
            token = item.strip().lower()
            if not token or token in stopwords:
                continue
            cleaned = token
            for word in stopwords:
                cleaned = cleaned.replace(word, "")
            cleaned = cleaned.strip()
            if len(cleaned) >= 2 and cleaned not in tokens:
                tokens.append(cleaned)

        return tokens

    def get_all_by_type(self, asset_type: AssetType) -> List[Asset]:
        """获取指定类型的所有资产"""
        self._ensure_loaded()
        return [a for a in self._assets.values() if a.asset_type == asset_type]


_master_data: Optional[AssetMasterData] = None


def get_asset_master() -> AssetMasterData:
    """获取全局资产主数据实例"""
    global _master_data
    if _master_data is None:
        _master_data = AssetMasterData()
    return _master_data
