#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 可演示闭环 smoke 测试
要求本地后端已启动，并开启 AGENT_V2_ENABLED=true。
"""

import json
import time
from typing import Dict, Iterable, List

import pytest
import requests


pytestmark = pytest.mark.smoke


def _unique_user() -> dict:
    timestamp = int(time.time() * 1000)
    return {
        "username": f"v2_smoke_{timestamp}",
        "password": "testpass123",
        "email": f"v2_smoke_{timestamp}@example.com",
    }


def _auth_headers(base_url: str) -> Dict[str, str]:
    user = _unique_user()
    response = requests.post(f"{base_url}/api/auth/register", json=user, timeout=10)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _submit_query(base_url: str, headers: Dict[str, str]) -> dict:
    response = requests.post(
        f"{base_url}/api/agent/v2/query",
        json={
            "query": "分析宁德时代未来三个月的风险",
            "preferences": {
                "debug_mode": True,
                "risk_preference": "稳健型",
                "investment_horizon": "三个月",
            },
        },
        headers=headers,
        timeout=15,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["task_id"]
    assert data["session_id"]
    assert data["status"] == "processing"
    return data


def _wait_for_completed_status(base_url: str, headers: Dict[str, str], task_id: str) -> dict:
    deadline = time.time() + 90
    last_status = None
    while time.time() < deadline:
        response = requests.get(
            f"{base_url}/api/agent/v2/status/{task_id}",
            headers=headers,
            timeout=10,
        )
        assert response.status_code == 200, response.text
        last_status = response.json()
        if last_status["status"] == "completed":
            return last_status
        if last_status["status"] in {"failed", "timeout"}:
            pytest.fail(f"V2 task failed: {last_status}")
        time.sleep(1)

    pytest.fail(f"V2 task did not complete before timeout: {last_status}")


def _iter_sse_events(response: requests.Response) -> Iterable[str]:
    event_type = None
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event_type:
            yield event_type
            event_type = None


def test_v2_health_enabled(base_url):
    """V2 health 应返回已启用"""
    response = requests.get(f"{base_url}/api/agent/v2/health", timeout=10)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ok"
    assert data["v2_enabled"] is True


def test_v2_query_requires_auth(base_url):
    """未授权提交 V2 query 必须返回 401"""
    response = requests.post(
        f"{base_url}/api/agent/v2/query",
        json={"query": "分析宁德时代"},
        timeout=10,
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"] == "未授权"


def test_v2_status_returns_result_shape(base_url):
    """V2 status 最终结果应包含前端依赖的核心结构"""
    headers = _auth_headers(base_url)
    task = _submit_query(base_url, headers)

    status = _wait_for_completed_status(base_url, headers, task["task_id"])
    result = status["result"]

    assert result["session_id"] == task["session_id"]
    assert "critic_result" in result
    assert "compliance_result" in result
    assert "evidence_items" in result
    assert "tool_results" in result
    if result.get("investment_answer"):
        assert isinstance(result["investment_answer"].get("scenarios", []), list)
    else:
        assert result.get("degraded") is True


def test_v2_sse_emits_expected_events(base_url):
    """SSE 应发出前端流程画布依赖的关键事件"""
    headers = _auth_headers(base_url)
    task = _submit_query(base_url, headers)
    token = headers["Authorization"].replace("Bearer ", "")
    expected = {
        "task_started",
        "node_started",
        "node_completed",
        "tool_started",
        "tool_completed",
        "evidence_added",
        "draft_created",
        "critic_completed",
        "compliance_completed",
        "task_completed",
    }

    with requests.get(
        f"{base_url}/api/agent/v2/events/{task['task_id']}",
        params={"token": token},
        stream=True,
        timeout=120,
    ) as response:
        assert response.status_code == 200, response.text
        seen: List[str] = []
        deadline = time.time() + 120
        for event_type in _iter_sse_events(response):
            seen.append(event_type)
            if expected.issubset(set(seen)):
                break
            if event_type in {"task_completed", "task_failed"}:
                break
            if time.time() > deadline:
                break

    missing = expected - set(seen)
    assert not missing, f"missing SSE events: {sorted(missing)}, seen={seen}"
