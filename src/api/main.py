#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask API 主应用
"""

import os
import sys
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
if CURRENT_DIR in sys.path:
    sys.path.remove(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_env_file() -> None:
    """加载项目根目录 .env，避免 V2 开关只在 shell 环境中生效"""
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

from models import init_db, get_db
from models.database import User
from api.auth import auth_bp, hash_password, verify_password
from api.agent import agent_bp
from api.stock import stock_bp
from api.news import news_bp
from api.chat import chat_bp
from api.feedback import feedback_bp
from api.eval_api import eval_bp
from api.auth import get_current_user

V2_ENABLED = os.getenv("AGENT_V2_ENABLED", "false").lower() == "true"
if V2_ENABLED:
    from api.agent_v2 import agent_v2_bp
    from api.events import events_bp

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    CORS(app)

    app.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logging.getLogger("werkzeug").setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    app.config["SECRET_KEY"] = "your-secret-key-change-in-production"

    init_db()

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(agent_bp, url_prefix="/api/agent")
    app.register_blueprint(stock_bp, url_prefix="/api/stock")
    app.register_blueprint(news_bp, url_prefix="/api/news")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(feedback_bp, url_prefix="/api")
    app.register_blueprint(eval_bp, url_prefix="/api/eval")

    if V2_ENABLED:
        app.register_blueprint(agent_v2_bp, url_prefix="/api/agent/v2")
        app.register_blueprint(events_bp, url_prefix="/api/agent/v2")
        logger.info("V2 Agent API 已启用")

    @app.route("/")
    def index():
        return jsonify(
            {"name": "AI投资分析系统 API", "version": "1.0.0", "status": "running"}
        )

    @app.route("/api/health")
    def health():
        from api.agent_executor import AgentWorkflowExecutor
        executor_count = len(AgentWorkflowExecutor._executors)
        processing_count = len([e for e in AgentWorkflowExecutor._executors.values() if e.status == "processing"])
        return jsonify({
            "status": "ok",
            "agents": {
                "active_executors": executor_count,
                "processing": processing_count,
            },
        })

    @app.before_request
    def _log_request_start():
        request._start_time = time.time()

    @app.after_request
    def _log_request_end(response):
        start_time = getattr(request, "_start_time", None)
        duration_ms = int((time.time() - start_time) * 1000) if start_time else -1
        logger.info(
            "HTTP %s %s -> %s (%sms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.route("/api/user/profile", methods=["GET"])
    def get_profile():
        """获取用户信息"""
        user = get_current_user()
        if not user:
            return jsonify({"error": "未授权"}), 401

        from utils.quota_manager import quota_manager
        user_tier = getattr(user, "user_tier", "free") or "free"
        quota_status = quota_manager.get_quota_status(user.id, user_tier)

        return jsonify(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "nickname": user.nickname,
                "user_tier": user_tier,
                "quota": quota_status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        ), 200

    @app.route("/api/user/profile", methods=["PUT"])
    def update_profile():
        """更新用户信息"""
        user = get_current_user()
        if not user:
            return jsonify({"error": "未授权"}), 401

        data = request.get_json()
        nickname = data.get("nickname")
        email = data.get("email")

        with get_db() as db:
            try:
                user_in_db = db.query(User).filter_by(id=user.id).first()
                if not user_in_db:
                    return jsonify({"error": "用户不存在"}), 404

                if nickname:
                    user_in_db.nickname = nickname

                if email and email != user_in_db.email:
                    existing_user = (
                        db.query(User)
                        .filter((User.email == email) & (User.id != user_in_db.id))
                        .first()
                    )
                    if existing_user:
                        return jsonify({"error": "邮箱已被使用"}), 400
                    user_in_db.email = email

                db.commit()

                return jsonify(
                    {
                        "message": "更新成功",
                        "user": {
                            "id": user_in_db.id,
                            "username": user_in_db.username,
                            "email": user_in_db.email,
                            "phone": user_in_db.phone,
                            "nickname": user_in_db.nickname,
                        },
                    }
                ), 200

            except Exception as e:
                db.rollback()
                return jsonify({"error": f"更新失败: {str(e)}"}), 500

    @app.route("/api/user/phone", methods=["PUT"])
    def update_phone():
        """更新手机号"""
        user = get_current_user()
        if not user:
            return jsonify({"error": "未授权"}), 401

        data = request.get_json() or {}
        phone = str(data.get("phone") or "").strip()
        if not phone:
            return jsonify({"error": "手机号不能为空"}), 400

        with get_db() as db:
            try:
                user_in_db = db.query(User).filter_by(id=user.id).first()
                if not user_in_db:
                    return jsonify({"error": "用户不存在"}), 404

                user_in_db.phone = phone
                db.commit()

                return jsonify(
                    {
                        "message": "手机号更新成功",
                        "user": {
                            "id": user_in_db.id,
                            "username": user_in_db.username,
                            "email": user_in_db.email,
                            "phone": user_in_db.phone,
                            "nickname": user_in_db.nickname,
                        },
                    }
                ), 200
            except Exception as e:
                db.rollback()
                return jsonify({"error": f"更新失败: {str(e)}"}), 500

    @app.route("/api/user/password", methods=["PUT"])
    def update_password():
        """更新密码"""
        user = get_current_user()
        if not user:
            return jsonify({"error": "未授权"}), 401

        data = request.get_json() or {}
        current_password = str(data.get("current_password") or "")
        new_password = str(data.get("new_password") or "")

        if not current_password or not new_password:
            return jsonify({"error": "缺少必要字段"}), 400
        if len(new_password) < 6:
            return jsonify({"error": "新密码长度不能少于 6 位"}), 400

        with get_db() as db:
            try:
                user_in_db = db.query(User).filter_by(id=user.id).first()
                if not user_in_db:
                    return jsonify({"error": "用户不存在"}), 404

                if not verify_password(current_password, user_in_db.password_hash):
                    return jsonify({"error": "原密码错误"}), 400

                user_in_db.password_hash = hash_password(new_password)
                db.commit()

                return jsonify({"message": "密码更新成功"}), 200
            except Exception as e:
                db.rollback()
                return jsonify({"error": f"更新失败: {str(e)}"}), 500

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "资源不存在"}), 404

    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({"error": "请求过于频繁，请稍后再试"}), 429

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception(f"内部错误: {str(error)}")
        return jsonify({"error": "服务器内部错误"}), 500

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "未授权"}), 401

    # ── 配额与升级相关路由 ──

    @app.route("/api/user/quota", methods=["GET"])
    def get_quota():
        """获取用户配额使用情况"""
        user = get_current_user()
        if not user:
            return jsonify({"error": "未授权"}), 401

        from utils.quota_manager import quota_manager
        user_tier = getattr(user, "user_tier", "free") or "free"
        quota_status = quota_manager.get_quota_status(user.id, user_tier)
        return jsonify(quota_status), 200

    @app.route("/api/user/tiers", methods=["GET"])
    def get_tiers():
        """获取所有等级信息"""
        from utils.quota_manager import quota_manager
        tiers = quota_manager.get_all_tiers()
        return jsonify({"tiers": tiers}), 200

    @app.route("/api/user/upgrade", methods=["POST"])
    def upgrade_tier():
        """升级用户等级"""
        user = get_current_user()
        if not user:
            return jsonify({"error": "未授权"}), 401

        data = request.get_json() or {}
        target_tier = data.get("tier", "").strip().lower()

        valid_tiers = ["free", "pro", "premium"]
        if target_tier not in valid_tiers:
            return jsonify({"error": f"无效的等级，可选: {', '.join(valid_tiers)}"}), 400

        from utils.quota_manager import TIER_LABELS
        current_tier = getattr(user, "user_tier", "free") or "free"
        tier_order = {"free": 0, "pro": 1, "premium": 2}
        if tier_order.get(target_tier, 0) <= tier_order.get(current_tier, 0):
            return jsonify({"error": "目标等级不能低于或等于当前等级"}), 400

        # 实际项目中此处应对接支付系统，目前直接升级
        with get_db() as db:
            try:
                user_in_db = db.query(User).filter_by(id=user.id).first()
                if not user_in_db:
                    return jsonify({"error": "用户不存在"}), 404

                user_in_db.user_tier = target_tier
                db.commit()

                return jsonify({
                    "message": f"已升级到{TIER_LABELS.get(target_tier, target_tier)}",
                    "user_tier": target_tier,
                    "tier_label": TIER_LABELS.get(target_tier, target_tier),
                }), 200
            except Exception as e:
                db.rollback()
                return jsonify({"error": f"升级失败: {str(e)}"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    debug_mode = os.getenv("FLASK_DEBUG", "1") == "1"
    use_reloader = os.getenv("FLASK_USE_RELOADER", "0") == "1"
    app.run(host="0.0.0.0", port=5001, debug=debug_mode, use_reloader=use_reloader)
