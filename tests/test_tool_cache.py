from agents.state import ToolResult
from analysts.registry import build_analyst
from agents.verifier import _caliber_core


def test_caliber_core():
    assert _caliber_core("PE(TTM)/近5年分位") == "PE(TTM)"
    assert _caliber_core("同业分位/PE(TTM)") == "PE(TTM)"
    assert _caliber_core("PB") == "PB"
    assert _caliber_core("合并报表") == ""


def test_tool_cache_reuses_same_params(monkeypatch):
    calls = []

    class FakeRegistry:
        def execute(self, name, params):
            calls.append((name, params))
            return ToolResult(tool_name=name, status="success", data={"value": 1})

    monkeypatch.setattr("tools.registry.get_tool_registry", lambda: FakeRegistry())
    agent = build_analyst("market", task_id="t", ledger=None, budget=None)
    first = agent._execute_tool("cn_stock_history", {"symbol": "600519"})
    second = agent._execute_tool("cn_stock_history", {"symbol": "600519"})
    other = agent._execute_tool("cn_stock_history", {"symbol": "000858"})
    assert len(calls) == 2
    assert second.data.get("_cache_hit") is True
    assert first.data.get("_cache_hit") is None
    assert other.data.get("_cache_hit") is None
