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

from models import init_db, get_db
from models.database import User
from api.auth import auth_bp, hash_password
from api.agent import agent_bp
from api.stock import stock_bp
from api.news import news_bp
from api.chat import chat_bp
from api.auth import get_current_user

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

    @app.route("/")
    def index():
        return jsonify(
            {"name": "AI投资分析系统 API", "version": "1.0.0", "status": "running"}
        )

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

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

        return jsonify(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "nickname": user.nickname,
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

                if user_in_db.password_hash != hash_password(current_password):
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

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception(f"内部错误: {str(error)}")
        return jsonify({"error": "服务器内部错误"}), 500

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "未授权"}), 401

    return app


if __name__ == "__main__":
    app = create_app()
    debug_mode = os.getenv("FLASK_DEBUG", "1") == "1"
    use_reloader = os.getenv("FLASK_USE_RELOADER", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode, use_reloader=use_reloader)
