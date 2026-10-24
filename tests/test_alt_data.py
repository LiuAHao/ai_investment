from data.alt_data import _fmt_yi, _num, _percentile


def test_percentile_basic():
    assert _percentile([10, 20, 30, 40], 20) == 50.0
    assert _percentile([10, 20, 30, 40], 40) == 100.0
    assert _percentile([], 10) is None
    assert _percentile([10, 20], None) is None


def test_percentile_ignores_invalid():
    assert _percentile([10, None, "bad", 30], 30) == 100.0


def test_fmt_yi():
    assert _fmt_yi(1.5e8) == "1.50 亿元"
    assert _fmt_yi(None) == "—"


def test_num():
    assert _num("1.5") == 1.5
    assert _num(None) is None
    assert _num("nan") is None
