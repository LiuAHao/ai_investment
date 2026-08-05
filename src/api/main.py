#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask API 主应用（多 Agent 重构版）
无登录、无配额，demo 形态。
"""

from __future__ import annotations

import logging
import os
import sys
import time

from flask import Flask, jsonify, request
from flask_cors import CORS

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
if CURRENT_DIR in sys.path:
    sys.path.remove(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_env_file() -> None:
    """加载项目根目录 .env"""
    env_path = os.path.abspath(os.path.join(PROJECT_ROOT, "..", ".env"))
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


_load_env_file()

from api.events import events_bp
from api.routes.agent import agent_bp
from api.routes.history import history_bp

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)
    CORS(app)

    app.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logging.getLogger("werkzeug").setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    app.config["SECRET_KEY"] = "ai-investment-demo"

    # 蓝图注册
    app.register_blueprint(agent_bp, url_prefix="/api/agent")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api/agent")

    @app.route("/")
    def index():
        return jsonify({"name": "AI投资分析系统 API", "version": "2.0.0", "status": "running"})

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": "2.0.0"})

    @app.before_request
    def _log_request_start():
        request._start_time = time.time()

    @app.after_request
    def _log_request_end(response):
        start_time = getattr(request, "_start_time", None)
        duration_ms = int((time.time() - start_time) * 1000) if start_time else -1
        logger.info("HTTP %s %s -> %s (%sms)", request.method, request.path, response.status_code, duration_ms)
        return response

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "资源不存在"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception("内部错误: %s", error)
        return jsonify({"error": "服务器内部错误"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    debug_mode = os.getenv("FLASK_DEBUG", "1") == "1"
    use_reloader = os.getenv("FLASK_USE_RELOADER", "0") == "1"
    port = int(os.getenv("FLASK_PORT") or os.getenv("PORT") or "5001")
    logger.info("启动 Flask API: port=%s", port)
    app.run(host="0.0.0.0", port=port, debug=debug_mode, use_reloader=use_reloader)
