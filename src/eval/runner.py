#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评测运行器
一键运行评测并生成报告
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from eval.case_loader import EvalCase, load_cases, get_available_datasets
from eval.rule_judge import RuleJudge
from eval.llm_judge import LLMJudge
from eval.metrics import (
    calculate_final_score,
    calculate_dataset_summary,
    calculate_category_summary,
    format_report,
)

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent / "reports"


class EvalRunner:
    """评测运行器"""

    def __init__(self, use_llm_judge: bool = True):
        self.rule_judge = RuleJudge()
        self.llm_judge = LLMJudge() if use_llm_judge else None
        self._results: List[Dict[str, Any]] = []

    def run_dataset(
        self,
        dataset_name: str,
        limit: Optional[int] = None,
        save_report: bool = True,
    ) -> Dict[str, Any]:
        """
        运行数据集评测
        
        Args:
            dataset_name: 数据集名称
            limit: 最大用例数
            save_report: 是否保存报告
            
        Returns:
            评测结果
        """
        logger.info("开始评测数据集: %s", dataset_name)
        
        cases = load_cases(dataset_name, limit)
        if not cases:
            logger.warning("数据集为空: %s", dataset_name)
            return {"error": "数据集为空"}
        
        run_id = str(uuid.uuid4())
        started_at = datetime.now()
        
        scores = []
        for i, case in enumerate(cases):
            logger.info("评测用例 %d/%d: %s", i + 1, len(cases), case.case_id)
            
            try:
                result = self._run_case(case)
                score = self._evaluate_case(case, result)
                score["case_id"] = case.case_id
                score["category"] = case.category
                scores.append(score)
            except Exception as e:
                logger.error("评测用例失败: %s, error: %s", case.case_id, e)
                scores.append({
                    "case_id": case.case_id,
                    "category": case.category,
                    "error": str(e),
                    "final_score": 0.0,
                })
        
        finished_at = datetime.now()
        
        summary = calculate_dataset_summary(scores)
        category_summary = calculate_category_summary(scores)
        
        report = {
            "run_id": run_id,
            "dataset_name": dataset_name,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "total_cases": len(cases),
            "summary": summary,
            "category_summary": category_summary,
            "scores": scores,
        }
        
        if save_report:
            self._save_report(report, dataset_name)
            self._save_to_db(report)
        
        report_text = format_report(summary, category_summary)
        logger.info("\n%s", report_text)
        
        return report

    def run_all(
        self,
        limit_per_dataset: Optional[int] = None,
        save_report: bool = True,
    ) -> Dict[str, Any]:
        """运行所有数据集评测"""
        datasets = get_available_datasets()
        
        all_reports = {}
        for dataset in datasets:
            report = self.run_dataset(dataset, limit_per_dataset, save_report=save_report)
            all_reports[dataset] = report
        
        return all_reports

    def _run_case(self, case: EvalCase) -> Dict[str, Any]:
        """运行单个用例"""
        from agent.v2.graph import run_v2_query
        
        result = run_v2_query(
            session_id=f"eval-{case.case_id}",
            user_id=0,
            query=case.query,
            chat_history=case.chat_history,
            user_profile=case.user_profile,
        )
        
        return result

    def _evaluate_case(self, case: EvalCase, result: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个用例"""
        rule_result = self.rule_judge.evaluate(case, result)
        rule_score = rule_result["rule_score"]
        details = rule_result["details"]
        
        llm_score = 0.0
        llm_details = {}
        if self.llm_judge:
            answer = result.get("final_answer", "")
            llm_details = self.llm_judge.evaluate(case.query, answer)
            llm_score = self.llm_judge.calculate_llm_score(llm_details)
        else:
            llm_score = rule_score
            llm_details = {"skipped": True, "reasoning": "未启用 LLM Judge，使用规则分参与合成"}
        
        compliance_score = details.get("compliance", 0.0)
        tool_selection_score = details.get("tool_selection", 0.0)
        context_score = details.get("context", 0.0)
        
        final_score = calculate_final_score(
            rule_score=rule_score,
            llm_score=llm_score,
            compliance_score=compliance_score,
            tool_selection_score=tool_selection_score,
            context_score=context_score,
        )
        
        return {
            "rule_score": rule_score,
            "llm_score": llm_score,
            "compliance_score": compliance_score,
            "tool_selection_score": tool_selection_score,
            "context_score": context_score,
            "final_score": final_score,
            "rule_details": details,
            "llm_details": llm_details,
        }

    def _save_report(self, report: Dict[str, Any], dataset_name: str) -> None:
        """保存评测报告"""
        REPORTS_DIR.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{dataset_name}_{timestamp}.json"
        filepath = REPORTS_DIR / filename
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            logger.info("评测报告已保存: %s", filepath)
        except Exception as e:
            logger.warning("保存报告失败: %s", e)

    def _save_to_db(self, report: Dict[str, Any]) -> None:
        """保存评测运行和分数到数据库"""
        try:
            from models import get_db, init_db
            from models.database import EvalRun, EvalScore

            init_db()
            summary = report.get("summary", {})
            scores = report.get("scores", [])
            started_at = datetime.fromisoformat(report["started_at"])
            finished_at = datetime.fromisoformat(report["finished_at"])

            with get_db() as db:
                run = EvalRun(
                    run_id=report["run_id"],
                    model_name=os.getenv("OPENAI_MODEL", ""),
                    prompt_version=os.getenv("AGENT_V2_PROMPT_VERSION", "v2"),
                    code_version=os.getenv("GIT_COMMIT", ""),
                    dataset_name=report["dataset_name"],
                    status="completed",
                    total_cases=report.get("total_cases", len(scores)),
                    passed_cases=sum(1 for score in scores if score.get("final_score", 0.0) >= 0.6),
                    avg_score=summary.get("avg_final_score", 0.0),
                    started_at=started_at,
                    finished_at=finished_at,
                    summary_json=json.dumps(summary, ensure_ascii=False),
                )
                db.add(run)

                for score in scores:
                    db.add(EvalScore(
                        run_id=report["run_id"],
                        case_id=score.get("case_id", ""),
                        rule_score=score.get("rule_score", 0.0),
                        llm_score=score.get("llm_score", 0.0),
                        compliance_score=score.get("compliance_score", 0.0),
                        context_score=score.get("context_score", 0.0),
                        tool_selection_score=score.get("tool_selection_score", 0.0),
                        final_score=score.get("final_score", 0.0),
                        details_json=json.dumps({
                            "rule_details": score.get("rule_details", {}),
                            "llm_details": score.get("llm_details", {}),
                            "error": score.get("error"),
                        }, ensure_ascii=False),
                    ))

                db.commit()
        except Exception as e:
            logger.warning("保存评测结果到数据库失败: %s", e)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="V2 自动化评测")
    parser.add_argument("--dataset", type=str, default=None, help="数据集名称")
    parser.add_argument("--limit", type=int, default=None, help="最大用例数")
    parser.add_argument("--no-llm", action="store_true", help="不使用 LLM 评分")
    parser.add_argument("--no-report", action="store_true", help="不保存评测报告和数据库记录")
    parser.add_argument("--list-datasets", action="store_true", help="列出可用数据集")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    if args.list_datasets:
        datasets = get_available_datasets()
        print("可用数据集:")
        for d in datasets:
            print(f"  - {d}")
        return
    
    runner = EvalRunner(use_llm_judge=not args.no_llm)
    
    if args.dataset:
        runner.run_dataset(args.dataset, args.limit, save_report=not args.no_report)
    else:
        runner.run_all(args.limit, save_report=not args.no_report)


if __name__ == "__main__":
    main()
