#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 API 基础 Schema 与任务服务测试
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.v2.schemas import QueryRequest
from services.task_service import TaskService


def test_query_request_validates_query_length():
    """V2 查询请求应校验 query 长度"""
    payload = QueryRequest.model_validate({"query": "分析宁德时代", "preferences": {"risk": "稳健"}})

    assert payload.query == "分析宁德时代"
    assert payload.preferences["risk"] == "稳健"


def test_task_service_records_user_id_for_authorization():
    """任务服务应记录 user_id，供状态查询做越权校验"""
    task_id = TaskService.create_task(session_id="session-test", user_id=123)
    task = TaskService.get_task(task_id)

    assert task is not None
    assert task.task_id == task_id
    assert task.session_id == "session-test"
    assert task.user_id == 123
