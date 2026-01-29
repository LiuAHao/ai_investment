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

            self._log(
                "StockAgent",
                "数据获取",
                "active",
                f"正在获取 {symbol} 的股票历史数据...",
                10,
            )
            stock_summary = self.master_agent.stock_agent.analyze_daily_hist(
                symbol=symbol
            )
            self._log(
                "StockAgent",
                "数据获取",
                "completed",
                f"成功获取 {symbol} 股票数据，共 {stock_summary.get('rows', 0)} 条记录",
                25,
            )

            self._log("StockAgent", "技术分析", "active", "正在计算技术指标...", 35)
            tech_indicators = (
                self.master_agent.stock_agent.analyze_technical_indicators(
                    symbol=symbol
                )
            )
            self._log("StockAgent", "技术分析", "completed", "技术指标计算完成", 45)

            self._log("NewsAgent", "新闻获取", "skipped", "主工作流已关闭新闻标题获取", 65)
            relevant_news = {
                "total_titles": 0,
                "relevant_titles": [],
            }

            self._log("DecisionAgent", "决策分析", "active", "正在生成投资建议...", 85)

            tool_results = [
                {
                    "name": "stock_analysis",
                    "args": {"symbol": symbol},
                    "result": stock_summary,
                },
                {
                    "name": "stock_tech",
                    "args": {"symbol": symbol},
                    "result": tech_indicators,
                },
            ]
            recommendation = self.master_agent.expert_agent.summarize(
                f"分析股票 {symbol}",
                tool_results,
                preferences,
            )

            result = {
                "symbol": symbol,
                "stock_summary": stock_summary,
                "tech_indicators": tech_indicators,
                "news_summary": {
                    "total_titles": 0,
                    "relevant_count": 0,
                    "relevant_titles": [],
                },
                "recommendation": recommendation,
                "timestamp": datetime.now().isoformat(),
            }

            self._log("DecisionAgent", "决策分析", "completed", "投资建议生成完成", 100)

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

            self._log("DecisionAgent", "任务拆解", "active", "正在分析用户查询...", 20)

            self._log(
                "DecisionAgent", "工具调用", "active", "正在调用数据获取工具...", 50
            )

            tool_results = self.master_agent.decision_agent.run_tools(user_query)
            if tool_results:
                step_base = 55
                step_span = 25
                step_count = len(tool_results)

                def format_args(value: object) -> str:
                    try:
                        text = json.dumps(value or {}, ensure_ascii=False, default=str)
                    except Exception:
                        text = "{}"
                    return text if len(text) <= 160 else f"{text[:160]}..."

                for idx, tool in enumerate(tool_results, start=1):
                    name = tool.get("name", "tool")
                    args = tool.get("args", {})
                    result = tool.get("result", {})
                    msg = f"工具 {name} 完成"
                    args_text = format_args(args)
                    if args_text and args_text != "{}":
                        msg += f", args={args_text}"
                    if isinstance(result, dict):
                        rows = result.get("rows")
                        if rows is not None:
                            msg += f", rows={rows}"
                        else:
                            keys = list(result.keys())
                            if keys:
                                msg += f", keys={keys[:6]}"
                    elif isinstance(result, list):
                        msg += f", items={len(result)}"

                    progress = step_base + int(step_span * idx / step_count)
                    self._log("DecisionAgent", f"工具结果-{name}", "completed", msg, progress)

            result_text = self.master_agent.expert_agent.summarize(
                user_query, tool_results, preferences
            )

            self._log("DecisionAgent", "结果生成", "completed", "查询结果生成完成", 100)

            self.status = "completed"
            self.result = {"response": result_text}
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
