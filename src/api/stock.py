#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票路由
"""

from flask import Blueprint, request, jsonify
from agent.stock_agent import StockAgent
from api.auth import get_current_user

stock_bp = Blueprint("stock", __name__)
stock_agent = StockAgent()


@stock_bp.route("/analyze", methods=["GET"])
def analyze():
    """股票分析"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    symbol = request.args.get("symbol")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    period = request.args.get("period", "daily")
    adjust = request.args.get("adjust", "")

    if not symbol:
        return jsonify({"error": "缺少股票代码"}), 400

    try:
        result = stock_agent.analyze_daily_hist(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            adjust=adjust,
        )
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"分析失败: {str(e)}"}), 500


@stock_bp.route("/technical", methods=["GET"])
def technical():
    """技术指标"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    symbol = request.args.get("symbol")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    period = request.args.get("period", "daily")
    adjust = request.args.get("adjust", "")
    ma_windows = request.args.getlist("ma_windows", type=int)

    if not symbol:
        return jsonify({"error": "缺少股票代码"}), 400

    try:
        result = stock_agent.analyze_technical_indicators(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            adjust=adjust,
            ma_windows=ma_windows or [5, 10, 20, 60],
        )
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"获取技术指标失败: {str(e)}"}), 500


@stock_bp.route("/history", methods=["GET"])
def history():
    """历史行情"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    symbol = request.args.get("symbol")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    period = request.args.get("period", "daily")
    adjust = request.args.get("adjust", "")

    if not symbol:
        return jsonify({"error": "缺少股票代码"}), 400

    try:
        result = stock_agent.fetch_daily_hist(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            adjust=adjust,
        )
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"获取历史行情失败: {str(e)}"}), 500


@stock_bp.route("/summary", methods=["GET"])
def summary():
    """股票汇总"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    symbol = request.args.get("symbol")

    if not symbol:
        return jsonify({"error": "缺少股票代码"}), 400

    try:
        result = stock_agent.summarize(symbol=symbol)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": f"获取汇总失败: {str(e)}"}), 500
