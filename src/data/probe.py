#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tushare 接口能力探测

长时间运行前先探测权限，避免"接口不可用但代码以为可用"的静默失败。
结果缓存在 src/data/capabilities.json（默认 24 小时）。
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

CAP_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "capabilities.json"))
_TTL_SECONDS = 24 * 3600


def _recent_dates(days: int = 400) -> tuple:
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    return start, end


def _probe_daily(client: Any) -> bool:
    start, end = _recent_dates(30)
    df = client.daily(ts_code="600519.SH", start_date=start, end_date=end)
    return df is not None and not df.empty


def _probe_stock_basic(client: Any) -> bool:
    df = client.stock_basic(ts_code="600519.SH", fields="ts_code,name,industry")
    return df is not None and not df.empty


def _probe_income(client: Any) -> bool:
    start, end = _recent_dates(800)
    df = client.income(ts_code="600519.SH", start_date=start, end_date=end)
    return df is not None and not df.empty and "ann_date" in df.columns


def _probe_fina(client: Any) -> bool:
    start, end = _recent_dates(800)
    df = client.fina_indicator(ts_code="600519.SH", start_date=start, end_date=end)
    return df is not None and not df.empty


def _probe_daily_basic(client: Any) -> bool:
    start, end = _recent_dates(30)
    df = client.daily_basic(ts_code="600519.SH", start_date=start, end_date=end)
    return df is not None and not df.empty


def _probe_anns(client: Any) -> bool:
    start, end = _recent_dates(180)
    df = client.anns_d(ts_code="600519.SH", start_date=start, end_date=end)
    return df is not None and not df.empty


def _probe_index(client: Any) -> bool:
    start, end = _recent_dates(60)
    df = client.index_daily(ts_code="000300.SH", start_date=start, end_date=end)
    return df is not None and not df.empty


def _probe_index_weight(client: Any) -> bool:
    start, end = _recent_dates(60)
    df = client.index_weight(index_code="000300.SH", start_date=start, end_date=end)
    return df is not None and not df.empty


def _probe_moneyflow(client: Any) -> bool:
    start, end = _recent_dates(30)
    df = client.moneyflow(ts_code="600519.SH", start_date=start, end_date=end)
    return df is not None and not df.empty


def _probe_macro(client: Any) -> bool:
    df = client.shibor(start_date=_recent_dates(60)[0], end_date=_recent_dates(60)[1])
    return df is not None and not df.empty


PROBES: Dict[str, Callable[[Any], bool]] = {
    "daily": _probe_daily,
    "stock_basic": _probe_stock_basic,
    "daily_basic": _probe_daily_basic,
    "index_daily": _probe_index,
    "income": _probe_income,
    "fina_indicator": _probe_fina,
    "anns_d": _probe_anns,
    "index_weight": _probe_index_weight,
    "moneyflow": _probe_moneyflow,
    "macro": _probe_macro,
}

CORE = ("daily", "stock_basic", "daily_basic", "index_daily")
DEEP = ("income", "fina_indicator", "anns_d", "index_weight", "moneyflow", "macro")


def probe_all(deep: bool = False, force: bool = False) -> Dict[str, Any]:
    """
    探测接口可用性。

    Args:
        deep: 是否探测财务/公告/资金等需要更高权限的接口
        force: 忽略缓存强制重新探测
    """
    cached = _load_cache()
    if cached and not force and (time.time() - float(cached.get("checked_at", 0)) < _TTL_SECONDS):
        if not deep or cached.get("deep"):
            return cached

    from data.tushare_client import get_client

    client = get_client()
    capabilities: Dict[str, bool] = {}
    if client is None:
        for name in (CORE + (DEEP if deep else ())):
            capabilities[name] = False
    else:
        for name in CORE + (DEEP if deep else ()):
            probe = PROBES.get(name)
            if not probe:
                continue
            try:
                capabilities[name] = bool(probe(client))
            except Exception as exc:  # noqa: BLE001
                logger.info("能力探测失败 %s: %s", name, str(exc)[:100])
                capabilities[name] = False

    payload = {
        "checked_at": time.time(),
        "checked_at_iso": datetime.now().isoformat(timespec="seconds"),
        "deep": bool(deep),
        "capabilities": capabilities,
    }
    _save_cache(payload)
    return payload


def is_available(name: str, default: bool = True) -> bool:
    """查询能力（未探测时返回 default，避免阻断正常流程）"""
    cached = _load_cache()
    if not cached:
        return default
    return bool((cached.get("capabilities") or {}).get(name, default))


def _load_cache() -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(CAP_FILE):
            return None
        with open(CAP_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:  # noqa: BLE001
        return None


def _save_cache(payload: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(CAP_FILE), exist_ok=True)
        with open(CAP_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("能力探测结果写入失败: %s", exc)
