#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评测结果 API
提供前端调试面板读取最近评测运行结果
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify

from api.auth import get_current_user

logger = logging.getLogger(__name__)

eval_bp = Blueprint("eval", __name__)


@eval_bp.route("/runs", methods=["GET"])
def list_eval_runs():
    """获取最近评测运行列表"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    try:
        from models import get_db, init_db
        from models.database import EvalRun

        init_db()
        with get_db() as db:
            runs = (
                db.query(EvalRun)
                .order_by(EvalRun.created_at.desc())
                .limit(20)
                .all()
            )

            data = []
            for run in runs:
                try:
                    summary = json.loads(run.summary_json or "{}")
                except Exception:
                    summary = {}

                data.append({
                    "run_id": run.run_id,
                    "dataset_name": run.dataset_name,
                    "status": run.status,
                    "total_cases": run.total_cases or 0,
                    "passed_cases": run.passed_cases or 0,
                    "avg_score": run.avg_score or 0.0,
                    "model_name": run.model_name,
                    "prompt_version": run.prompt_version,
                    "code_version": run.code_version,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "summary_json": summary,
                })

            return jsonify({"runs": data}), 200
    except Exception as exc:
        logger.error("获取评测运行失败: %s", exc)
        return jsonify({"error": f"获取评测运行失败: {str(exc)}"}), 500
