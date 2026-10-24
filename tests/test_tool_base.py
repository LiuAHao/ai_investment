#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""工具结果状态测试（避免"成功但空数据"误导模型）"""

from __future__ import annotations

from tools.base import BaseTool


class _EmptyFailTool(BaseTool):
    name = "empty_fail"
    description = "test"

    def execute(self, **kwargs):
        return {"error": "tushare 不可用", "evidence": []}


class _PartialTool(BaseTool):
    name = "partial"
    description = "test"

    def execute(self, **kwargs):
        return {"error": "部分接口失败", "evidence": [{"statement": "有效证据"}]}


class _RaiseTool(BaseTool):
    name = "raise"
    description = "test"

    def execute(self, **kwargs):
        raise RuntimeError("boom")


def test_error_without_payload_is_failed():
    result = _EmptyFailTool().run()
    assert result.status == "failed"
    assert "tushare" in (result.error or "")


def test_error_with_payload_stays_success():
    result = _PartialTool().run()
    assert result.status == "success"
    assert result.data["error"] == "部分接口失败"


def test_exception_is_failed():
    result = _RaiseTool().run()
    assert result.status == "failed"
    assert "boom" in (result.error or "")
