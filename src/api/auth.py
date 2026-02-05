#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
认证路由
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
import hashlib
from models.database import User
from utils.jwt_utils import create_access_token, decode_access_token
from models import get_db

auth_bp = Blueprint("auth", __name__)


def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


@auth_bp.route("/register", methods=["POST"])
def register():
    """用户注册"""
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    nickname = data.get("nickname", username)
    phone = data.get("phone")

    if not all([username, email, password]):
        return jsonify({"error": "缺少必要字段"}), 400

    with get_db() as db:
        try:
            existing_user = (
                db.query(User)
                .filter((User.username == username) | (User.email == email))
                .first()
            )

            if existing_user:
                return jsonify({"error": "用户名或邮箱已存在"}), 400

            user = User(
                username=username,
                email=email,
                phone=phone,
                password_hash=hash_password(password),
                nickname=nickname,
            )
            db.add(user)
            db.commit()

            token = create_access_token({"user_id": user.id, "username": user.username})

            return jsonify(
                {
                    "message": "注册成功",
                    "token": token,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "phone": user.phone,
                        "nickname": user.nickname,
                    },
                }
            ), 201

        except Exception as e:
            db.rollback()
            return jsonify({"error": f"注册失败: {str(e)}"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """用户登录"""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not all([username, password]):
        return jsonify({"error": "缺少用户名或密码"}), 400

    with get_db() as db:
        try:
            if "@" in username:
                user = db.query(User).filter_by(email=username).first()
            else:
                user = db.query(User).filter_by(username=username).first()

            if not user or user.password_hash != hash_password(password):
                return jsonify({"error": "用户名或密码错误"}), 401

            if not user.is_active:
                return jsonify({"error": "账户已被禁用"}), 401

            token = create_access_token({"user_id": user.id, "username": user.username})

            return jsonify(
                {
                    "message": "登录成功",
                    "token": token,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "phone": user.phone,
                        "nickname": user.nickname,
                    },
                }
            ), 200

        except Exception as e:
            return jsonify({"error": f"登录失败: {str(e)}"}), 500


def get_current_user():
    """获取当前用户"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    payload = decode_access_token(token)

    if not payload:
        return None

    with get_db() as db:
        user = db.query(User).filter_by(id=payload.get("user_id")).first()
        return user
