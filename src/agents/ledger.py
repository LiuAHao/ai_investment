#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
证据台账（EvidenceLedger）

设计要点：
1. 工具执行成功后由代码自动登记，不依赖模型输出 [FINDINGS]
2. 每条证据有全局单调 ID（EV-0001），下游只能引用台账内的事实
3. 按 (asset_id, category, 归一化 statement) 去重，保留最新一次观测
4. 支持 as_of（回测 PIT）：来源时间晚于决策时点的证据标记 conflict
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from agents.state import LedgerEvidence
from utils import pit

# 工具名 → 证据类别
TOOL_CATEGORY: Dict[str, str] = {
    "cn_stock_history": "market",
    "us_stock_history": "market",
    "fund_nav_history": "valuation",
    "fund_profile": "fundamental",
    "etf_profile": "valuation",
    "etf_tracking_index": "valuation",
    "stock_financial_summary": "fundamental",
    "stock_fund_flow": "flow",
    "stock_expectation": "fundamental",
    "stock_valuation_band": "valuation",
    "stock_events": "announcement",
    "industry_context": "market",
    "hk_stock_history": "market",
    "stock_financial_indicator": "fundamental",
    "stock_peer_compare": "fundamental",
    "asset_news_search": "news",
    "web_research": "news",
    "macro_indicator": "macro",
    "index_environment": "macro",
}

# 常见的"数值 + 单位"字段（用于抽取可核验的数字）
_SCALAR_KEYS = (
    ("latest_close", ""), ("total_return_pct", "%"), ("latest_change_pct", "%"),
    ("volatility_pct", "%"), ("momentum_pct", "%"), ("PE", "倍"),
    ("PE_TTM", "倍"), ("PB", "倍"), ("ps_ttm", "倍"),
    ("revenue", ""), ("revenue_yoy", "%"), ("net_profit", ""),
    ("net_profit_yoy", "%"), ("gross_margin", "%"), ("roe", "%"),
    ("debt_ratio", "%"), ("operating_cashflow", ""),
)


# 常见字段 → 中文标签（用于把工具返回的 dict 转成可读语句）
FIELD_LABELS = {
    "latest_close": "收盘",
    "total_return_pct": "区间涨跌幅",
    "latest_change_pct": "最新涨跌幅",
    "volatility_pct": "波动率",
    "momentum_pct": "动量",
    "PE": "PE",
    "PE_TTM": "PE(TTM)",
    "PB": "PB",
    "PS_TTM": "PS(TTM)",
    "股息率(%)": "股息率",
    "换手率(%)": "换手率",
    "总市值(万)": "总市值",
    "流通市值(万)": "流通市值",
    "rows": "记录数",
    "start_date": "起始日",
    "end_date": "截止日",
    "trend": "趋势",
    "source": "数据源",
    "total_titles": "新闻数",
}

_PUNCT_RE = re.compile(r"[\s，。；、,.;:：!？\"'（）()\[\]【】]+")


class EvidenceLedger:
    """线程安全的证据台账"""

    def __init__(self, as_of: Optional[str] = None):
        self.as_of = as_of or pit.get_as_of()
        self._lock = threading.Lock()
        self._items: List[LedgerEvidence] = []
        self._by_id: Dict[str, LedgerEvidence] = {}
        self._dedup: Dict[str, str] = {}  # dedup_key -> evidence_id
        self._counter = 0

    # ---------- 写入 ----------

    def add(self, item: LedgerEvidence) -> LedgerEvidence:
        """写入一条证据（去重合并）"""
        statement = (item.statement or "").strip()
        if not statement:
            statement = "（工具返回空摘要）"
            item.statement = statement
        if not item.evidence_id:
            with self._lock:
                self._counter += 1
                item.evidence_id = f"EV-{self._counter:04d}"
        if not item.retrieved_at:
            item.retrieved_at = datetime.now().isoformat(timespec="seconds")

        # PIT 校验：来源时间晚于决策时点 → 标记冲突并降权
        if self.as_of and item.source_time and pit.is_after(item.source_time, self.as_of):
            item.conflict = True
            item.confidence = min(item.confidence, 0.1)

        key = self._dedup_key(item.asset_id, item.category, statement)
        with self._lock:
            existing_id = self._dedup.get(key)
            if existing_id:
                existing = self._by_id[existing_id]
                existing.seen_count += 1
                existing.retrieved_at = item.retrieved_at
                if item.source_time:
                    existing.source_time = item.source_time
                if item.conflict:
                    existing.conflict = True
                return existing
            if item.evidence_id in self._by_id:
                # 调用方自带 ID 且重复：追加序号避免覆盖
                self._counter += 1
                item.evidence_id = f"EV-{self._counter:04d}"
            self._items.append(item)
            self._by_id[item.evidence_id] = item
            self._dedup[key] = item.evidence_id
            return item

    def record_tool(
        self,
        agent: str,
        tool_name: str,
        params: Dict[str, Any],
        result: Any,
        asset_id: str = "",
    ) -> List[LedgerEvidence]:
        """
        工具调用后自动登记证据。

        Args:
            agent: 调用方（仅用于审计，不写入证据语义）
            tool_name: 工具名
            params: 工具入参
            result: ToolResult
            asset_id: 指定资产（缺省从参数推断）

        Returns:
            本次新写入/合并的证据列表
        """
        status = getattr(result, "status", "")
        data = getattr(result, "data", None) or {}
        if status not in ("success", "partial") or not data:
            return []

        asset = asset_id or self._guess_asset_id(params, data)
        category = TOOL_CATEGORY.get(tool_name, "market")
        source_url = self._first_url(data)
        source_time = self._extract_source_time(data)

        # 工具可以显式提供结构化证据（优先）
        explicit = data.get("evidence")
        items: List[LedgerEvidence] = []
        if isinstance(explicit, list):
            for raw in explicit:
                if not isinstance(raw, dict):
                    continue
                statement = str(raw.get("statement") or raw.get("fact") or "").strip()
                if not statement:
                    continue
                items.append(LedgerEvidence(
                    evidence_id="",
                    asset_id=str(raw.get("asset_id") or asset),
                    category=str(raw.get("category") or category),
                    statement=statement,
                    value=raw.get("value"),
                    unit=str(raw.get("unit") or ""),
                    caliber=str(raw.get("caliber") or ""),
                    source_tool=tool_name,
                    source_url=str(raw.get("source_url") or source_url),
                    source_time=str(raw.get("source_time") or source_time),
                    confidence=float(raw.get("confidence", 0.85) or 0.85),
                    raw_ref=str(raw.get("raw_ref") or ""),
                ))

        if not items:
            value, unit = self._extract_scalar(data)
            items.append(LedgerEvidence(
                evidence_id="",
                asset_id=asset,
                category=category,
                statement=self._extract_statement(tool_name, data),
                value=value,
                unit=unit,
                caliber=self._extract_caliber(data),
                source_tool=tool_name,
                source_url=source_url,
                source_time=source_time,
                confidence=0.8 if status == "success" else 0.6,
                raw_ref=getattr(result, "step_id", "") or "",
            ))

        return [self.add(item) for item in items if item.statement.strip()]

    # ---------- 读取 ----------

    def get(self, evidence_id: str) -> Optional[LedgerEvidence]:
        return self._by_id.get(evidence_id)

    def all(self) -> List[LedgerEvidence]:
        with self._lock:
            return list(self._items)

    def reindex(self) -> None:
        """按 (category, asset, statement) 稳定排序并重新编号，保证回测可复现"""
        with self._lock:
            items = sorted(
                self._items,
                key=lambda item: (item.category, item.asset_id, item.statement),
            )
            self._items = items
            self._by_id = {}
            self._dedup = {}
            self._counter = 0
            for item in items:
                self._counter += 1
                item.evidence_id = f"EV-{self._counter:04d}"
                self._by_id[item.evidence_id] = item
                self._dedup[self._dedup_key(item.asset_id, item.category, item.statement)] = item.evidence_id

    def ids(self) -> List[str]:
        with self._lock:
            return [item.evidence_id for item in self._items]

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def by_category(self) -> Dict[str, List[LedgerEvidence]]:
        grouped: Dict[str, List[LedgerEvidence]] = {}
        for item in self.all():
            grouped.setdefault(item.category, []).append(item)
        return grouped

    def validate(self, evidence_ids: Iterable[str]) -> List[str]:
        """返回不存在的 evidence_id 列表"""
        return [eid for eid in evidence_ids if eid not in self._by_id]

    def format_for_prompt(
        self,
        categories: Optional[Iterable[str]] = None,
        limit_per_category: int = 12,
        include_conflict: bool = True,
    ) -> str:
        """
        格式化台账供 prompt 使用。按类别配额截断，避免上下文膨胀。
        """
        grouped = self.by_category()
        allowed = set(categories) if categories else None
        lines: List[str] = []
        for category in sorted(grouped.keys()):
            if allowed is not None and category not in allowed:
                continue
            items = grouped[category]
            items = [i for i in items if include_conflict or not i.conflict]
            if not items:
                continue
            lines.append(f"### {category}")
            for item in items[:limit_per_category]:
                flags = []
                if item.caliber:
                    flags.append(item.caliber)
                if item.source_time:
                    flags.append(f"时间 {item.source_time}")
                if item.conflict:
                    flags.append("⚠ 晚于决策时点")
                suffix = f"（{'；'.join(flags)}）" if flags else ""
                value = f" = {item.value}{item.unit}" if item.value not in (None, "") else ""
                lines.append(f"[{item.evidence_id}] {item.statement}{value}{suffix}")
            if len(items) > limit_per_category:
                lines.append(f"…（该类共 {len(items)} 条，其余略）")
        return "\n".join(lines) if lines else "（证据台账为空）"

    def summary(self) -> Dict[str, int]:
        grouped = self.by_category()
        return {category: len(items) for category, items in grouped.items()}

    # ---------- 提取辅助 ----------

    @staticmethod
    def _dedup_key(asset_id: str, category: str, statement: str) -> str:
        normalized = _PUNCT_RE.sub("", statement.lower())
        raw = f"{asset_id}|{category}|{normalized}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _guess_asset_id(params: Dict[str, Any], data: Dict[str, Any]) -> str:
        for key in ("symbol", "fund_code", "code", "ticker"):
            value = params.get(key) or data.get(key)
            if value:
                return str(value)
        keywords = params.get("keywords")
        if isinstance(keywords, list) and keywords:
            return str(keywords[0])
        return ""

    @staticmethod
    def _first_url(data: Dict[str, Any]) -> str:
        direct = data.get("source_url") or data.get("url")
        if direct:
            return str(direct)
        for key in ("web_results", "results", "items", "relevant_titles"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        link = item.get("link") or item.get("url")
                        if link:
                            return str(link)
        return ""

    @staticmethod
    def _extract_source_time(data: Dict[str, Any]) -> str:
        for key in ("source_time", "published_at", "timestamp", "ann_date",
                    "trade_date", "date", "as_of"):
            value = data.get(key)
            if value:
                return str(value)[:19]
        summary = data.get("summary")
        if isinstance(summary, dict):
            for key in ("end_date", "latest_date", "trade_date", "日期"):
                if summary.get(key):
                    return str(summary[key])[:19]
        return ""

    @staticmethod
    def _extract_statement(tool_name: str, data: Dict[str, Any]) -> str:
        """按工具生成可读语句；无法识别时退化为"字段 值"而非 JSON dump"""
        if tool_name == "cn_stock_history":
            text = _market_statement(data)
            if text:
                return text
        if tool_name == "fund_nav_history":
            text = _fund_nav_statement(data)
            if text:
                return text
        if tool_name in ("asset_news_search", "web_research"):
            text = _news_statement(data)
            if text:
                return text

        summary = data.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()[:400]
        if isinstance(summary, dict):
            parts = [
                f"{FIELD_LABELS.get(key, key)} {_fmt_number(value)}"
                for key, value in summary.items()
                if value not in (None, "", [], {})
            ]
            if parts:
                return "，".join(parts[:5])[:400]
        for key in ("relevant_titles", "titles"):
            titles = data.get(key)
            if isinstance(titles, list) and titles:
                return "新闻：" + "；".join(str(t) for t in titles[:3])[:400]
        for key in ("web_results", "results", "items", "data"):
            rows = data.get(key)
            if isinstance(rows, list) and rows:
                first = rows[0]
                if isinstance(first, dict):
                    title = first.get("title") or first.get("名称") or first.get("name")
                    if title:
                        return f"{title}"[:400]
                return f"返回 {len(rows)} 条记录"
        return f"{tool_name} 返回数据"

    @staticmethod
    def _extract_scalar(data: Dict[str, Any]) -> tuple:
        candidates: List[Dict[str, Any]] = []
        for key in ("summary", "technical", "valuation", "quote", "profile", "data"):
            value = data.get(key)
            if isinstance(value, dict):
                candidates.append(value)
        candidates.append(data)
        for container in candidates:
            for key, unit in _SCALAR_KEYS:
                raw = container.get(key)
                if isinstance(raw, (int, float)):
                    return raw, unit
                if isinstance(raw, str):
                    try:
                        return float(raw.replace("%", "").replace(",", "")), unit
                    except ValueError:
                        continue
        return None, ""

    @staticmethod
    def _extract_caliber(data: Dict[str, Any]) -> str:
        for key in ("caliber", "口径", "adjust", "pe_type"):
            value = data.get(key)
            if value:
                return str(value)
        valuation = data.get("valuation")
        if isinstance(valuation, dict) and valuation.get("PE_TTM") is not None:
            return "PE(TTM)"
        return ""


# ==================== 语句模板 ====================

def _fmt_number(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}".rstrip("0").rstrip(".")
    return str(value)[:60]


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):+.1f}%"
    except (TypeError, ValueError):
        return ""


def _market_statement(data: Dict[str, Any]) -> str:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    technical = data.get("technical") if isinstance(data.get("technical"), dict) else {}
    valuation = data.get("valuation") if isinstance(data.get("valuation"), dict) else {}
    parts: List[str] = []

    close = summary.get("latest_close")
    if close is not None:
        parts.append(f"收盘 {_fmt_number(close)}")
    ret = summary.get("total_return_pct")
    if ret is not None:
        parts.append(f"区间 {_fmt_pct(ret)}")
    change = summary.get("latest_change_pct")
    if change is not None:
        parts.append(f"最新 {_fmt_pct(change)}")

    ma_parts = []
    for window in (5, 20, 60):
        value = technical.get(f"ma_{window}")
        if value is not None:
            ma_parts.append(f"MA{window} {_fmt_number(value)}")
    if ma_parts:
        parts.append("，".join(ma_parts))

    trend = technical.get("trend")
    if trend:
        parts.append(f"趋势{trend}")

    pe = valuation.get("PE_TTM") or valuation.get("PE")
    if pe is not None:
        parts.append(f"PE(TTM) {_fmt_number(pe)}")
    pb = valuation.get("PB")
    if pb is not None:
        parts.append(f"PB {_fmt_number(pb)}")

    return "，".join(parts)[:400]


def _spot_statement(data: Dict[str, Any]) -> str:
    rows = data.get("data") or data.get("rows") or []
    if not isinstance(rows, list) or not rows:
        return ""
    first = rows[0] if isinstance(rows[0], dict) else {}
    code = first.get("代码") or first.get("symbol") or ""
    close = first.get("收盘") or first.get("close")
    pct = first.get("涨跌幅") or first.get("pct_chg")
    text = f"快照 {len(rows)} 条"
    if code:
        text += f"，{code}"
    if close is not None:
        text += f" 收盘 {_fmt_number(close)}"
    if pct is not None:
        text += f"（{_fmt_pct(pct)}）"
    return text


def _fund_nav_statement(data: Dict[str, Any]) -> str:
    rows = data.get("nav_data") or []
    if not isinstance(rows, list) or not rows:
        return ""
    latest = rows[-1] if isinstance(rows[-1], dict) else {}
    nav = latest.get("单位净值") or latest.get("unit_nav")
    date = latest.get("净值日期") or latest.get("nav_date") or ""
    if nav is None:
        return ""
    return f"最新净值 {_fmt_number(nav)}" + (f"（{date}）" if date else "")


def _news_statement(data: Dict[str, Any]) -> str:
    titles = data.get("relevant_titles") or []
    if isinstance(titles, list) and titles:
        return "新闻：" + "；".join(str(t) for t in titles[:3])[:350]
    rows = data.get("web_results") or data.get("results") or []
    if isinstance(rows, list) and rows:
        picked = [
            str(item.get("title") or "")
            for item in rows[:3]
            if isinstance(item, dict) and item.get("title")
        ]
        if picked:
            return "新闻：" + "；".join(picked)[:350]
    return ""
