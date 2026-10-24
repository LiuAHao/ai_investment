from agents.ledger import EvidenceLedger
from agents.pipeline import _localize_horizon, _readable_conclusion, _strip_chatter
from agents.state import AnalystOutput, LedgerEvidence


def _output(evidence=None, gaps=None) -> AnalystOutput:
    return AnalystOutput(analyst="Test", evidence=evidence or [], gaps=gaps or [])


def test_truncated_json_never_returns_raw_json():
    raw = (
        '{"decision":"final","conclusion":"市场处于中期上涨后的加速调整阶段，流动性宽松不构成下跌主因",'
        '"gap'
    )
    text = _readable_conclusion(raw, _output([]))
    assert not text.lstrip().startswith('{"decision"')
    assert "市场处于中期上涨后的加速调整阶段" in text


def test_plain_text_filters_chatter():
    raw = "市场偏弱，成交缩量。\n需要我进一步做行业分析吗？"
    text = _readable_conclusion(raw, _output())
    assert "市场偏弱" in text
    assert "需要我" not in text


def test_normal_json_uses_highlights_and_counts():
    raw = '{"decision":"final","highlights":[{"statement":"营收同比 12.5%"}],"gaps":[{"question":"毛利率"}]}'
    text = _readable_conclusion(
        raw,
        _output(
            [LedgerEvidence(evidence_id="EV-1", statement="a")],
            [{"question": "毛利率", "reason": "缺少财报"}],
        ),
    )
    assert "采集 1 条证据" in text
    assert "1 个问题未覆盖" in text
    assert "营收同比 12.5%" in text


def test_empty_output_still_has_headline():
    text = _readable_conclusion("", _output())
    assert text == "完成取证"


def test_horizon_localized():
    assert _localize_horizon("medium") == "中期 1-6 个月"
    assert _localize_horizon("short") == "短期 1-4 周"
    assert _localize_horizon("long") == "长期 6 个月以上"
    assert _localize_horizon("") == "中期 1-6 个月"
    assert _localize_horizon("3 个月") == "3 个月"


def test_strip_chatter_keeps_content():
    text = _strip_chatter("结论 A\n是否需要我继续？\n结论 B")
    assert "结论 A" in text and "结论 B" in text
    assert "是否需要我" not in text


def test_market_statement_is_readable():
    text = EvidenceLedger._extract_statement(
        "cn_stock_history",
        {
            "summary": {"latest_close": 3658.03, "total_return_pct": -6.0, "latest_change_pct": -1.2},
            "technical": {"ma_5": 3710.73, "ma_20": 3813.14, "trend": "下行"},
            "valuation": {"PE_TTM": 12.78, "PB": 1.35},
        },
    )
    assert "收盘 3658.03" in text
    assert "区间 -6.0%" in text
    assert "MA5 3710.73" in text
    assert "PE(TTM) 12.78" in text
    assert "latest_close" not in text


def test_generic_statement_does_not_dump_json():
    text = EvidenceLedger._extract_statement(
        "some_tool",
        {"summary": {"latest_close": 10.5, "total_return_pct": 2.0}},
    )
    assert "收盘 10.5" in text
    assert "latest_close" not in text


def test_macro_field_formatting():
    from data.macro_client import _fmt_field

    assert _fmt_field("nt_val", 100.9) == "当月值 100.9"
    assert _fmt_field("nt_yoy", 0.9) == "同比 +0.9%"
    assert _fmt_field("nt_mom", -0.2) == "环比 -0.2%"
    assert _fmt_field("on", 1.36) == "隔夜 1.36%"
    assert _fmt_field("2w", 1.40) == "2周 1.40%"
