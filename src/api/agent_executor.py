#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent工作流执行器
"""

import uuid
import threading
import logging
import json
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from agent.master_agent import MasterAgent
from agent.stock_agent import StockAgent
from agent.news_agent import NewsAgent
from models.database import AnalysisSession, AgentLog
from models import SessionLocal

logger = logging.getLogger(__name__)


class AgentWorkflowExecutor:
    """Agent工作流执行器"""

    _executors: Dict[str, "AgentWorkflowExecutor"] = {}
    _lock = threading.Lock()

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.db: Optional[Session] = None
        self.master_agent = MasterAgent()
        self.progress = 0
        self.status = "pending"
        self.result = None
        self.error = None
        self.logs = []

    @classmethod
    def get_executor(cls, session_id: str, db: Optional[Session] = None) -> "AgentWorkflowExecutor":
        """获取或创建执行器实例"""
        with cls._lock:
            if session_id not in cls._executors:
                executor = cls(session_id)
                cls._executors[session_id] = executor
            return cls._executors[session_id]

    @classmethod
    def remove_executor(cls, session_id: str):
        """移除执行器实例"""
        with cls._lock:
            if session_id in cls._executors:
                del cls._executors[session_id]

    def _log(
        self, agent_name: str, step_name: str, status: str, message: str, progress: int
    ):
        """记录日志"""
        if not self.db:
            return
        log_entry = {
            "agent": agent_name,
            "text": message,
            "status": status,
            "progress": progress,
        }
        self.logs.append(log_entry)

        agent_log = AgentLog(
            session_id=self.session_id,
            agent_name=agent_name,
            step_name=step_name,
            status=status,
            log_message=message,
            progress_pct=progress,
        )
        self.db.add(agent_log)
        self.db.commit()

        self.progress = progress
        session = (
            self.db.query(AnalysisSession)
            .filter_by(session_id=self.session_id)
            .first()
        )
        if session:
            session.progress = progress
            session.status = "processing" if status == "active" else session.status
            self.db.commit()

    def run_analysis(self, symbol: str, news_limit: int = 20, preferences: Optional[Dict] = None):
        """执行分析工作流"""
        self.db = SessionLocal()
        try:
            self.status = "processing"
            self.progress = 5
            self._log("系统", "初始化", "active", "启动分析工作流", 5)

            session = (
                self.db.query(AnalysisSession)
                .filter_by(session_id=self.session_id)
                .first()
            )
            if session:
                session.status = "processing"
                session.progress = 5
                self.db.commit()

            self._log("MasterAgent", "任务分解", "active", "正在生成任务计划...", 15)
            workflow_result = self.master_agent.execute_phase2(
                user_query=f"分析股票 {symbol}",
                preferences=preferences,
            )

            result_map = {
                item.get("agent"): item
                for item in workflow_result.get("agent_results", [])
            }

            progress_cursor = 30
            for agent_name in ["StockAgent", "NewsAgent", "KnowledgeAgent", "AnalysisAgent"]:
                item = result_map.get(agent_name)
                if not item:
                    continue
                status = item.get("status", "failed")
                log_status = "completed" if status == "completed" else ("skipped" if status == "skipped" else "failed")
                text = "阶段完成"
                if status == "failed":
                    text = f"阶段失败: {item.get('error') or '未知错误'}"
                elif status == "skipped":
                    text = item.get("error") or "阶段跳过"
                self._log(agent_name, "阶段执行", log_status, text, progress_cursor)
                progress_cursor += 15

            data_payload = result_map.get("StockAgent", {}).get("data", {})
            news_payload = result_map.get("NewsAgent", {}).get("data", {})
            recommendation = workflow_result.get("recommendation", "")

            result = {
                "symbol": symbol,
                "stock_summary": data_payload.get("summary", {}),
                "tech_indicators": data_payload.get("technical", {}),
                "news_summary": news_payload,
                "recommendation": recommendation,
                "degraded": workflow_result.get("degraded", False),
                "task_plan": workflow_result.get("task_plan", {}),
                "agent_results": workflow_result.get("agent_results", []),
                "timestamp": datetime.now().isoformat(),
            }

            self._log("MasterAgent", "结果汇总", "completed", "投资建议生成完成", 100)

            self.status = "completed"
            self.result = result
            self.progress = 100

            if session:
                session.status = "completed"
                session.progress = 100
                session.result_summary = json.dumps(result, ensure_ascii=False, default=str)
                self.db.commit()

            logger.info(f"分析完成: session_id={self.session_id}, symbol={symbol}")

        except Exception as e:
            logger.error(f"分析失败: session_id={self.session_id}, error={str(e)}")
            self.status = "failed"
            self.error = str(e)
            self._log("系统", "错误", "failed", f"分析失败: {str(e)}", self.progress)

            session = (
                self.db.query(AnalysisSession)
                .filter_by(session_id=self.session_id)
                .first()
            )
            if session:
                session.status = "failed"
                session.error_message = str(e)
                self.db.commit()
        finally:
            if self.db:
                self.db.close()
                self.db = None

    def run_query(self, user_query: str, preferences: Optional[Dict] = None):
        """执行查询工作流"""
        self.db = SessionLocal()
        try:
            self.status = "processing"
            self.progress = 5
            self._log("系统", "初始化", "active", "启动查询工作流", 5)

            session = (
                self.db.query(AnalysisSession)
                .filter_by(session_id=self.session_id)
                .first()
            )
            if session:
                session.status = "processing"
                session.progress = 5
                self.db.commit()

            self._log("MasterAgent", "任务拆解", "active", "正在分析用户查询...", 20)

            workflow_result = self.master_agent.execute_phase2(
                user_query=user_query,
                preferences=preferences,
            )

            result_map = {
                item.get("agent"): item
                for item in workflow_result.get("agent_results", [])
            }
            progress_cursor = 45
            for agent_name in ["StockAgent", "NewsAgent", "KnowledgeAgent", "AnalysisAgent"]:
                item = result_map.get(agent_name)
                if not item:
                    continue
                status = item.get("status", "failed")
                log_status = "completed" if status == "completed" else ("skipped" if status == "skipped" else "failed")
                msg = "阶段执行完成"
                if status == "failed":
                    msg = f"阶段失败: {item.get('error') or '未知错误'}"
                elif status == "skipped":
                    msg = item.get("error") or "阶段跳过"
                self._log(agent_name, "阶段执行", log_status, msg, progress_cursor)
                progress_cursor += 12

            self._log("MasterAgent", "结果生成", "active", "正在生成查询结果...", 92)
            result_text = workflow_result.get("recommendation", "")
            self._log("MasterAgent", "结果生成", "completed", "查询结果生成完成", 100)

            self.status = "completed"
            self.result = {
                "response": result_text,
                "degraded": workflow_result.get("degraded", False),
                "task_plan": workflow_result.get("task_plan", {}),
                "agent_results": workflow_result.get("agent_results", []),
            }
            self.progress = 100

            if session:
                session.status = "completed"
                session.progress = 100
                session.result_summary = result_text
                self.db.commit()

            logger.info(f"查询完成: session_id={self.session_id}")

        except Exception as e:
            logger.error(f"查询失败: session_id={self.session_id}, error={str(e)}")
            self.status = "failed"
            self.error = str(e)
            self._log("系统", "错误", "failed", f"查询失败: {str(e)}", self.progress)

            session = (
                self.db.query(AnalysisSession)
                .filter_by(session_id=self.session_id)
                .first()
            )
            if session:
                session.status = "failed"
                session.error_message = str(e)
                self.db.commit()
        finally:
            if self.db:
                self.db.close()
                self.db = None

    def get_status(self) -> Dict:
        """获取执行状态"""
        return {
            "session_id": self.session_id,
            "status": self.status,
            "progress": self.progress,
            "logs": self.logs,
            "result": self.result,
            "error": self.error,
        }
