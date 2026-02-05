#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
查询轻量索引（无向量版）
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _load_config(config_path: Path) -> Dict[str, object]:
    return json.loads(config_path.read_text(encoding="utf-8"))


def _load_index(index_path: Path) -> Dict[str, object]:
    return json.loads(index_path.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str) -> List[str]:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
    tokens = [t for t in cleaned.split(" ") if t]
    if tokens:
        return tokens
    return [ch for ch in cleaned if ch.strip()]


def _score(query_tokens: List[str], text: str) -> int:
    score = 0
    for token in query_tokens:
        score += text.count(token)
    return score


def _rank_chunks(chunks: Iterable[Dict[str, str]], query: str, top_k: int) -> List[Dict[str, object]]:
    normalized_query = _normalize(query)
    query_tokens = _tokenize(normalized_query)

    ranked: List[Tuple[int, Dict[str, str]]] = []
    for chunk in chunks:
        text = _normalize(chunk.get("text", ""))
        score = _score(query_tokens, text)
        if score > 0:
            ranked.append((score, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    results: List[Dict[str, object]] = []
    for score, chunk in ranked[:top_k]:
        results.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "title": chunk.get("title"),
                "text": chunk.get("text"),
                "score": score,
                "source_path": chunk.get("source_path"),
            }
        )
    return results


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    config_path = base_dir / "config" / "rag_config.json"
    config = _load_config(config_path)

    index_dir = base_dir / config["index"]["index_dir"]
    index_path = index_dir / config["index"]["index_file"]
    if not index_path.exists():
        raise FileNotFoundError(f"未找到索引文件: {index_path}")

    index_data = _load_index(index_path)
    chunks = index_data.get("chunks", [])

    query = input("请输入查询问题: ").strip()
    if not query:
        print("查询为空，已退出。")
        return

    top_k = int(config["query"]["top_k"])
    results = _rank_chunks(chunks, query, top_k)

    print(json.dumps({"query": query, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
