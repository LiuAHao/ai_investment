#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
用户配额管理器
基于内存 + 数据库的每日配额控制，支持 free / pro / premium 三个等级。
"""

import threading
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 各等级每日配额 ──
TIER_QUOTAS: Dict[str, Dict[str, int]] = {
    "free": {
        "analysis_per_day": 5,       # 每日分析/查询次数
        "chat_per_day": 20,          # 每日聊天次数
    },
    "pro": {
        "analysis_per_day": 30,
        "chat_per_day": 100,
    },
    "premium": {
        "analysis_per_day": 100,
        "chat_per_day": 500,
    },
}

# ── 等级中文名 ──
TIER_LABELS: Dict[str, str] = {
    "free": "免费版",
    "pro": "专业版",
    "premium": "旗舰版",
}

# ── 等级描述 ──
TIER_DESCRIPTIONS: Dict[str, str] = {
    "free": "基础分析功能，每日5次分析额度",
    "pro": "专业分析功能，每日30次分析额度",
    "premium": "无限制专业分析，每日100次分析额度",
}


class QuotaManager:
    """基于内存的每日配额管理器"""

    def __init__(self):
        self._usage: Dict[str, int] = {}
        self._lock = threading.Lock()

    def _make_key(self, user_id: int, resource: str) -> str:
        """生成 usage key：user_id:resource:date"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return f"{user_id}:{resource}:{today}"

    def _get_limit(self, user_tier: str, resource: str) -> int:
        """获取指定等级的资源限额"""
        tier = user_tier if user_tier in TIER_QUOTAS else "free"
        return TIER_QUOTAS[tier].get(resource, 0)

    def check_and_consume(
        self,
        user_id: int,
        resource: str,
        user_tier: str = "free",
        amount: int = 1,
    ) -> Tuple[bool, Dict]:
        """
        检查配额并消耗

        Args:
            user_id: 用户ID
            resource: 资源类型（analysis_per_day / chat_per_day）
            user_tier: 用户等级
            amount: 消耗数量

        Returns:
            (是否允许, 配额详情)
        """
        limit = self._get_limit(user_tier, resource)
        if limit <= 0:
            return True, {"limit": 0, "used": 0, "remaining": 0}

        key = self._make_key(user_id, resource)
        with self._lock:
            current = self._usage.get(key, 0)
            if current + amount > limit:
                return False, {
                    "limit": limit,
                    "used": current,
                    "remaining": max(0, limit - current),
                    "tier": user_tier,
                    "tier_label": TIER_LABELS.get(user_tier, "免费版"),
                }
            self._usage[key] = current + amount
            return True, {
                "limit": limit,
                "used": current + amount,
                "remaining": limit - current - amount,
                "tier": user_tier,
                "tier_label": TIER_LABELS.get(user_tier, "免费版"),
            }

    def get_quota_status(self, user_id: int, user_tier: str = "free") -> Dict:
        """获取用户每日配额使用情况"""
        tier = user_tier if user_tier in TIER_QUOTAS else "free"
        result = {}
        for resource, limit in TIER_QUOTAS[tier].items():
            key = self._make_key(user_id, resource)
            with self._lock:
                used = self._usage.get(key, 0)
            result[resource] = {
                "used": used,
                "limit": limit,
                "remaining": max(0, limit - used),
            }
        result["tier"] = tier
        result["tier_label"] = TIER_LABELS.get(tier, "免费版")
        return result

    def get_all_tiers(self) -> list:
        """返回所有等级信息"""
        tiers = []
        for tier_key in ["free", "pro", "premium"]:
            quotas = TIER_QUOTAS[tier_key]
            tiers.append({
                "tier": tier_key,
                "label": TIER_LABELS[tier_key],
                "description": TIER_DESCRIPTIONS[tier_key],
                "quotas": quotas,
            })
        return tiers


# 全局单例
quota_manager = QuotaManager()
