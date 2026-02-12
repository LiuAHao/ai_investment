#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
证券代码解析器
优先使用本地主数据做公司名 -> 股票代码解析，降低对在线接口的依赖。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SymbolResolver:
    """公司名/别名到股票代码解析器"""

    def __init__(self, master_file: Optional[str] = None, cache_ttl_seconds: int = 3600):
        default_file = Path(__file__).resolve().parents[1] / "stock" / "data" / "stock_zh_a_spot_em.txt"
        self.master_file = Path(master_file) if master_file else default_file
        self.cache_ttl_seconds = cache_ttl_seconds
        self._records: List[Dict[str, Any]] = []
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._load_master_data()

    @staticmethod
    def _normalize(text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"[\s\-_/()（）]+", "", text)
        return text

    @staticmethod
    def _extract_code(text: str) -> Optional[str]:
        if not text:
            return None
        pattern = r"(?<!\d)(?:[A-Za-z]{2})?(\d{6})(?:\.(?:SZ|SS|SH|BJ))?(?!\d)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1)

    @staticmethod
    def _extract_name_candidates(text: str) -> List[str]:
        stopwords = {
            "分析",
            "财报",
            "走势",
            "后期",
            "影响",
            "今天",
            "今日",
            "复盘",
            "资金",
            "流向",
            "建议",
            "风险",
            "提示",
            "一下",
            "请问",
            "请",
            "关于",
            "以及",
            "后市",
            "如何",
        }
        terms = re.findall(r"[\u4e00-\u9fa5]{2,10}", text or "")
        candidates: List[str] = []
        for term in terms:
            if term in stopwords:
                continue
            stripped = term
            for sw in stopwords:
                stripped = stripped.replace(sw, "")
            stripped = stripped.strip()
            if len(stripped) < 2:
                continue
            if stripped not in candidates:
                candidates.append(stripped)
        return candidates

    def _load_master_data(self) -> None:
        if not self.master_file.exists():
            self._records = []
            return

        try:
            if self.master_file.suffix.lower() == ".json":
                data = json.loads(self.master_file.read_text(encoding="utf-8"))
                self._records = data if isinstance(data, list) else []
                return

            lines = self.master_file.read_text(encoding="utf-8").splitlines()
            records: List[Dict[str, Any]] = []
            for line in lines:
                content = (line or "").strip()
                if not content:
                    continue
                if "代码" in content and "名称" in content:
                    continue

                parts = re.split(r"\s+", content, maxsplit=1)
                if len(parts) < 2:
                    continue

                symbol = parts[0].strip()
                name = parts[1].strip()
                if not re.fullmatch(r"\d{6}", symbol):
                    continue
                if not name:
                    continue

                records.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "aliases": [],
                        "pinyin": [],
                    }
                )

            dedup: Dict[str, Dict[str, Any]] = {}
            for record in records:
                dedup.setdefault(record["symbol"], record)
            self._records = list(dedup.values())
        except Exception:
            self._records = []

    def _match_record(self, query: str) -> List[Dict[str, Any]]:
        query_text = query or ""
        query_norm = self._normalize(query_text)
        name_candidates = self._extract_name_candidates(query_text)

        scored: List[Tuple[int, Dict[str, Any]]] = []
        for record in self._records:
            symbol = str(record.get("symbol") or "").strip()
            name = str(record.get("name") or "").strip()
            aliases = [str(item).strip() for item in (record.get("aliases") or []) if str(item).strip()]
            pinyins = [str(item).strip().lower() for item in (record.get("pinyin") or []) if str(item).strip()]

            if not symbol or not name:
                continue

            score = 0
            if name and name in query_text:
                score = max(score, 100)

            for alias in aliases:
                if alias and alias in query_text:
                    score = max(score, 95)

            norm_name = self._normalize(name)
            if norm_name and norm_name in query_norm:
                score = max(score, 90)

            for alias in aliases:
                norm_alias = self._normalize(alias)
                if norm_alias and norm_alias in query_norm:
                    score = max(score, 85)

            for py in pinyins:
                py_norm = self._normalize(py)
                if py_norm and py_norm in query_norm:
                    score = max(score, 70)

            if score == 0:
                for cand in name_candidates:
                    if cand == name:
                        score = max(score, 80)
                    if cand in aliases:
                        score = max(score, 75)

            if score > 0:
                scored.append((score, {"symbol": symbol, "name": name, "score": score}))

        scored.sort(key=lambda item: item[0], reverse=True)

        unique: List[Dict[str, Any]] = []
        seen = set()
        for _, item in scored:
            symbol = item["symbol"]
            if symbol in seen:
                continue
            seen.add(symbol)
            unique.append(item)
        return unique

    def resolve(self, query: str) -> Dict[str, Any]:
        code = self._extract_code(query)
        if code:
            return {
                "symbol": code,
                "method": "explicit_code",
                "confidence": 1.0,
                "candidates": [],
            }

        key = self._normalize(query)
        cached = self._cache.get(key)
        if cached:
            ts, payload = cached
            if time.time() - ts <= self.cache_ttl_seconds:
                return payload
            self._cache.pop(key, None)

        candidates = self._match_record(query)
        if not candidates:
            payload = {
                "symbol": None,
                "method": "not_found",
                "confidence": 0.0,
                "candidates": [],
            }
            self._cache[key] = (time.time(), payload)
            return payload

        best = candidates[0]
        same_score = [item for item in candidates if item["score"] == best["score"]]
        if len(same_score) > 1:
            payload = {
                "symbol": best["symbol"],
                "method": "ambiguous_pick",
                "confidence": 0.6,
                "candidates": [
                    {"symbol": item["symbol"], "name": item["name"]}
                    for item in candidates[:5]
                ],
            }
        else:
            payload = {
                "symbol": best["symbol"],
                "method": "offline_master",
                "confidence": min(1.0, best["score"] / 100.0),
                "candidates": [
                    {"symbol": item["symbol"], "name": item["name"]}
                    for item in candidates[1:4]
                ],
            }

        self._cache[key] = (time.time(), payload)
        return payload
