#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库表结构验证脚本
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect

# 加载 .env
env_path = Path(__file__).resolve().parent / ".env"
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("未检测到 DATABASE_URL")
        return 1

    try:
        engine = create_engine(database_url, echo=False)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print("数据库连接成功！")
        print(f"已创建的表: {len(tables)} 个")
        
        expected_tables = ["users", "chat_history", "analysis_sessions", "agent_logs"]
        for table_name in expected_tables:
            if table_name in tables:
                columns = inspector.get_columns(table_name)
                print(f"\n✓ {table_name} ({len(columns)} 个字段)")
                for col in columns:
                    print(f"  - {col['name']}: {col['type']}")
            else:
                print(f"\n✗ {table_name} 不存在")
        
        return 0
    except Exception as exc:
        print(f"验证失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
