#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""LLM JSON 提取测试（推理模型会先输出思考再给 JSON）"""

from __future__ import annotations

from agents.llm import extract_json_object, extract_json_objects


def test_extracts_json_after_reasoning_text():
    text = '用户想让我输出计划。我先想想。{"intent":"macro","focus_questions":["a"]}'
    data = extract_json_object(text)
    assert data["intent"] == "macro"


def test_skips_invalid_braces_and_finds_real_json():
    text = '先看这个例子 {not valid json} 然后真正的答案 {"stance":"bullish","conviction":0.7}'
    data = extract_json_object(text)
    assert data["stance"] == "bullish"


def test_recovers_truncated_json():
    text = '{"side":"bear","claims":[{"claim_id":"C1","statement":"营收下滑'
    objects = extract_json_objects(text)
    assert objects
    assert objects[0]["side"] == "bear"
    assert objects[0]["claims"][0]["claim_id"] == "C1"


def test_returns_all_candidates():
    text = '{"a":1} 中间说明 {"b":2}'
    objects = extract_json_objects(text)
    assert {"a": 1} in objects
    assert {"b": 2} in objects
