#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新闻路由
"""

from flask import Blueprint, request, jsonify
from agent.news_agent import NewsAgent
from api.auth import get_current_user

news_bp = Blueprint("news", __name__)
news_agent = NewsAgent()


@news_bp.route("/titles", methods=["GET"])
def titles():
    """获取新闻标题"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    limit = request.args.get("limit", 50, type=int)

    try:
        titles = news_agent.fetch_titles(limit=limit)
        return jsonify({"titles": titles, "count": len(titles)}), 200

    except Exception as e:
        return jsonify({"error": f"获取新闻标题失败: {str(e)}"}), 500


@news_bp.route("/filter", methods=["POST"])
def filter():
    """按关键词筛选新闻"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    keywords = data.get("keywords", [])
    titles = data.get("titles")

    if not keywords:
        return jsonify({"error": "缺少关键词"}), 400

    try:
        result = news_agent.filter_by_keywords(titles or [], keywords)
        return jsonify({"filtered_news": result, "count": len(result)}), 200

    except Exception as e:
        return jsonify({"error": f"筛选失败: {str(e)}"}), 500


@news_bp.route("/relevant", methods=["POST"])
def relevant():
    """获取相关新闻"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    keywords = data.get("keywords", [])
    limit = data.get("limit", 50)

    if not keywords:
        return jsonify({"error": "缺少关键词"}), 400

    try:
        result = news_agent.get_relevant_titles(keywords=keywords, limit=limit)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"获取相关新闻失败: {str(e)}"}), 500
