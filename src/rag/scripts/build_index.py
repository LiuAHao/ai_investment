#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
构建轻量检索索引（无向量版）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def _load_config(config_path: Path) -> Dict[str, object]:
    return json.loads(config_path.read_text(encoding="utf-8"))


def _load_chunks(chunks_path: Path) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    config_path = base_dir / "config" / "rag_config.json"
    config = _load_config(config_path)

    chunks_dir = base_dir / config["data"]["chunks_dir"]
    index_dir = base_dir / config["index"]["index_dir"]
    index_dir.mkdir(parents=True, exist_ok=True)

    chunks_path = chunks_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"未找到知识块文件: {chunks_path}")

    chunks = _load_chunks(chunks_path)

    index_data = {
        "version": "simple-v1",
        "chunks": chunks,
    }

    index_path = index_dir / config["index"]["index_file"]
    index_path.write_text(json.dumps(index_data, ensure_ascii=False), encoding="utf-8")

    print(f"已构建索引: {index_path}")
    print(f"索引条目数量: {len(chunks)}")


if __name__ == "__main__":
    main()
