#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
后端启动脚本
"""

import os
import sys
import logging

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.api.main import create_app
from src.models import init_db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    init_db()
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
