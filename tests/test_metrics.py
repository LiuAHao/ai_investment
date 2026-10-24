#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""回测指标测试"""

from __future__ import annotations

import pytest

from backtest.metrics import (
    brier_score,
    calibration_table,
    is_hit,
    is_unstable,
    majority_stance,
    summarize,
)


def test_is_hit_by_stance():
    assert is_hit("bullish", 0.05) is True
    assert is_hit("bullish", -0.01) is False
    assert is_hit("bearish", -0.05) is True
    assert is_hit("neutral", 0.01) is True
    assert is_hit("neutral", 0.10) is False


def test_brier_score():
    assert brier_score(1.0, True) == 0.0
    assert brier_score(0.0, True) == 1.0
    assert brier_score(0.8, True) == pytest.approx(0.04)


def test_majority_and_stability():
    assert majority_stance(["bullish", "bullish", "neutral"]) == "bullish"
    assert is_unstable(["bullish", "bearish", "bullish"]) is True
    assert is_unstable(["bullish", "bullish"]) is False


def test_calibration_and_summary():
    records = [
        {"stance": "bullish", "conviction": 0.9, "ret": 0.10, "alpha": 0.05, "hit": True, "debate_enabled": True},
        {"stance": "bullish", "conviction": 0.85, "ret": -0.02, "alpha": -0.01, "hit": False, "debate_enabled": True},
        {"stance": "bearish", "conviction": 0.5, "ret": -0.05, "alpha": 0.01, "hit": True, "debate_enabled": False},
        {"stance": "neutral", "conviction": 0.3, "ret": 0.01, "alpha": 0.0, "hit": True, "debate_enabled": False},
    ]
    table = calibration_table(records)
    assert table[3]["samples"] == 2
    assert table[3]["hit_rate"] == 0.5

    summary = summarize(records)
    assert summary["settled"] == 4
    assert summary["hit_rate"] == 0.75
    assert summary["brier"] is not None
    assert summary["by_stance"]["bullish"]["samples"] == 2
    assert summary["debate_lift"] is not None


def test_summary_excludes_unstable():
    records = [
        {"stance": "bullish", "conviction": 0.8, "ret": 0.1, "hit": True, "unstable": False},
        {"stance": "bearish", "conviction": 0.8, "ret": -0.1, "hit": True, "unstable": True},
    ]
    summary = summarize(records)
    assert summary["settled"] == 1
    assert summary["unstable"] == 1
