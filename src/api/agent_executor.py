#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent工作流执行器
"""

import uuid
import time
import threading
import logging
import json
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from agent.master_agent import MasterAgent
from agent.news_agent import NewsAgent
from models.database import AnalysisSession, AgentLog
from models import SessionLocal

logger = logging.getLogger(__name__)


class AgentWorkflowExecutor:
    """Agent工作流执行器"""

    _executors: Dict[str, "AgentWorkflowExecutor"] = {}
    _lock = threading.Lock()
    _cleanup_started = False
    _CLEANUP_INTERVAL = 300   # 5分钟清理一次
    _EXPIRE_SECONDS = 3600    # 已完成任务保留1小时

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.db: Optional[Session] = None
        self.master_agent = MasterAgent()
        self.progress = 0
        self.status = "pending"
        self.result = None
        self.error = None
        self.logs = []
        self.agent_results = []  # 存储实时的Agent结果
        self._completion_time: Optional[float] = None
        self._agent_progress_map = {
            "DataAgent": 30,
            "NewsAgent": 50,
            "KnowledgeAgent": 70,
            "AnalysisAgent": 90,
        }

    @classmethod
    def _start_cleanup_thread(cls):
        """启动后台清理线程（只启动一次）"""
        if cls._cleanup_started:
            return
        cls._cleanup_started = True
        t = threading.Thread(target=cls._cleanup_loop, daemon=True)
        t.start()

    @classmethod
    def _cleanup_loop(cls):
        """后台定期清理已完成的执行器"""
        import time as _time
        while True:
            _time.sleep(cls._CLEANUP_INTERVAL)
            cls._do_cleanup()

    @classmethod
    def _do_cleanup(cls):
        """清理过期的执行器实例"""
        import time as _time
        now = _time.time()
        with cls._lock:
            to_remove = [
                sid for sid, ex in cls._executors.items()
                if ex.status in ("completed", "failed")
                and ex._completion_time is not None
                and now - ex._completion_time > cls._EXPIRE_SECONDS
            ]
            for sid in to_remove:
                del cls._executors[sid]
            if to_remove:
                logger.info("清理了 %d 个过期执行器", len(to_remove))

    @classmethod
    def get_executor(cls, session_id: str, db: Optional[Session] = None) -> "AgentWorkflowExecutor":
        """获取或创建执行器实例"""
        cls._start_cleanup_thread()
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

    def _on_agent_complete(self, agent_name: str, agent_result: Dict):
        """Agent完成时的回调函数，实时更新结果"""
        self.agent_results.append(agent_result)
        progress = self._agent_progress_map.get(agent_name, self.progress)
        
        # 生成Agent总结文本
        summary = self._generate_agent_summary(agent_name, agent_result)
        status = agent_result.get("status", "completed")
        log_status = "completed" if status == "completed" else ("skipped" if status == "skipped" else "failed")
        
        self._log(agent_name, "阶段执行", log_status, summary, progress)
        
        # 更新中间结果到数据库
        if self.db:
            session = (
                self.db.query(AnalysisSession)
                .filter_by(session_id=self.session_id)
                .first()
            )
            if session:
                # 保存当前已完成的Agent结果
                intermediate_result = {
                    "agent_results": self.agent_results,
                    "progress": progress,
                    "status": "processing",
                }
                session.result_summary = json.dumps(intermediate_result, ensure_ascii=False, default=str)
                session.progress = progress
                self.db.commit()
    
    def _generate_agent_summary(self, agent_name: str, agent_result: Dict) -> str:
        """根据Agent结果生成详细总结文本"""
        status = agent_result.get("status", "")
        data = agent_result.get("data", {})
        error = agent_result.get("error", "")
        
        if status == "failed":
            return f"执行失败: {error or '未知错误'}"
        
        if status == "skipped":
            reason = data.get("reason") or error or "该阶段已跳过"
            return f"已跳过: {reason}"
        
        if agent_name == "DataAgent":
            summary = data.get("summary", {})
            technical = data.get("technical", {})
            if not summary and not technical:
                return "当前查询不涉及具体股票分析"
            symbol = summary.get("symbol", "")
            parts = []
            if symbol:
                parts.append(f"股票 {symbol} 数据采集完成")
            if summary.get("start_date") and summary.get("end_date"):
                parts.append(f"分析区间: {summary['start_date']} ~ {summary['end_date']}")
            if summary.get("latest_close") is not None:
                close_text = f"收盘价 ¥{summary['latest_close']:.2f}"
                if summary.get("latest_change_pct") is not None:
                    sign = "+" if summary["latest_change_pct"] >= 0 else ""
                    close_text += f"（{sign}{summary['latest_change_pct']:.2f}%）"
                parts.append(close_text)
            if summary.get("total_return_pct") is not None:
                trend_word = "上涨" if summary["total_return_pct"] >= 0 else "下跌"
                parts.append(f"区间涨跌: {trend_word} {abs(summary['total_return_pct']):.2f}%")
            if summary.get("high_max") is not None and summary.get("low_min") is not None:
                parts.append(f"价格区间: ¥{summary['low_min']:.2f} ~ ¥{summary['high_max']:.2f}")
            if summary.get("volatility_pct") is not None:
                parts.append(f"波动率: {summary['volatility_pct']:.2f}%")
            if technical.get("trend"):
                ma_info = ""
                ma_vals = technical.get("ma", {})
                if ma_vals:
                    ma_strs = [f"{k.upper()}: ¥{v:.2f}" for k, v in ma_vals.items()]
                    ma_info = f"（{', '.join(ma_strs)}）"
                parts.append(f"技术趋势: {technical['trend']}{ma_info}")
            if technical.get("momentum_pct") is not None:
                parts.append(f"短期动量: {technical['momentum_pct']:+.2f}%")
            return "；".join(parts) if parts else "股票数据采集完成"
        
        if agent_name == "NewsAgent":
            web_results = data.get("web_results", [])
            relevant_titles = data.get("relevant_titles", [])
            total = data.get("total_titles", len(relevant_titles))
            parts = []
            if total > 0:
                parts.append(f"获取 {total} 条相关新闻")
            if web_results:
                parts.append(f"网络搜索补充 {len(web_results)} 条市场信息")
                # 展示前几条搜索结果标题
                for item in web_results[:3]:
                    title = item.get("title", "")
                    if title:
                        parts.append(f"• {title}")
            if not parts:
                parts.append("未检索到直接相关的新闻资讯")
            return "；".join(parts[:1]) + ("。" if parts else "") + "\n".join(parts[1:]) if len(parts) > 1 else parts[0]
        
        if agent_name == "KnowledgeAgent":
            results = data.get("results", [])
            citations = data.get("citations", [])
            fallback = data.get("fallback", False)
            if not results:
                return "未找到匹配的知识片段，将基于通用分析框架继续评估"
            parts = [f"从知识库提取了 {len(results)} 条相关知识"]
            if citations:
                titles = list({c.get("title", "") for c in citations if c.get("title")})
                if titles:
                    parts.append(f"参考来源: {', '.join(titles[:4])}")
            if fallback:
                parts.append("知识库覆盖不足，将结合通用框架补充分析")
            return "；".join(parts)
        
        if agent_name == "AnalysisAgent":
            recommendation = data.get("recommendation", "")
            if recommendation:
                # 截取前150字作为摘要
                excerpt = recommendation[:150].replace("\n", " ")
                if len(recommendation) > 150:
                    excerpt += "…"
                return f"综合分析完成: {excerpt}"
            return "综合分析完成"
        
        return "阶段执行完成"

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

    def run_analysis(self, symbol: str, news_limit: int = 20, preferences: Optional[Dict] = None, user_query: Optional[str] = None):
        """执行分析工作流"""
        if not user_query:
            user_query = f"分析股票 {symbol}"
        self.db = SessionLocal()
        self.agent_results = []  # 重置Agent结果
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
            
            # 使用回调机制执行工作流
            workflow_result = self.master_agent.execute_phase2(
                user_query=user_query,
                preferences=preferences,
                on_agent_complete=self._on_agent_complete,
            )

            data_payload = {}
            news_payload = {}
            for item in workflow_result.get("agent_results", []):
                if item.get("agent") == "DataAgent":
                    data_payload = item.get("data", {})
                elif item.get("agent") == "NewsAgent":
                    news_payload = item.get("data", {})
            
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
            self._completion_time = time.time()

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
            self._completion_time = time.time()
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
        self.agent_results = []  # 重置Agent结果
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

            # 使用回调机制执行工作流
            workflow_result = self.master_agent.execute_phase2(
                user_query=user_query,
                preferences=preferences,
                on_agent_complete=self._on_agent_complete,
            )

            self._log("MasterAgent", "结果生成", "completed", "查询结果生成完成", 100)
            result_text = workflow_result.get("recommendation", "")

            self.status = "completed"
            self.result = {
                "response": result_text,
                "degraded": workflow_result.get("degraded", False),
                "task_plan": workflow_result.get("task_plan", {}),
                "agent_results": workflow_result.get("agent_results", []),
            }
            self.progress = 100
            self._completion_time = time.time()

            if session:
                session.status = "completed"
                session.progress = 100
                session.result_summary = json.dumps(self.result, ensure_ascii=False, default=str)
                self.db.commit()

            logger.info(f"查询完成: session_id={self.session_id}")

        except Exception as e:
            logger.error(f"查询失败: session_id={self.session_id}, error={str(e)}")
            self.status = "failed"
            self.error = str(e)
            self._completion_time = time.time()
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
