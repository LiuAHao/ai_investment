#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
查询 Chroma 向量索引，并支持 rerank
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
from sentence_transformers import CrossEncoder, SentenceTransformer


def _load_config(config_path: Path) -> Dict[str, object]:
    return json.loads(config_path.read_text(encoding="utf-8"))


def _rerank(
    query: str,
    items: List[Dict[str, object]],
    model_name: str,
    top_k: int,
) -> List[Dict[str, object]]:
    if not items:
        return []

    pairs = [(query, str(item.get("text", ""))) for item in items]
    model = CrossEncoder(model_name)
    scores = model.predict(pairs)

    ranked: List[Tuple[float, Dict[str, object]]] = []
    for score, item in zip(scores, items):
        rerank_item = dict(item)
        rerank_item["rerank_score"] = float(score)
        ranked.append((float(score), rerank_item))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in ranked[:top_k]]


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    config_path = base_dir / "config" / "rag_config.json"
    config = _load_config(config_path)

    chroma_dir = base_dir / config["chroma"]["persist_dir"]
    collection_name = str(config["chroma"]["collection"])

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(name=collection_name)

    query = input("请输入查询问题: ").strip()
    if not query:
        print("查询为空，已退出。")
        return

    model_name = str(config["embedding"]["model_name"])
    local_only = bool(config.get("hf", {}).get("local_files_only", False))
    embedder = SentenceTransformer(model_name, local_files_only=local_only)
    query_embedding = embedder.encode([query], normalize_embeddings=True).tolist()[0]

    top_k = int(config["query"]["top_k"])
    result = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    items: List[Dict[str, object]] = []
    for index in range(len(result.get("ids", [[]])[0])):
        items.append(
            {
                "chunk_id": result["ids"][0][index],
                "text": result["documents"][0][index],
                "metadata": result["metadatas"][0][index],
                "distance": result["distances"][0][index],
            }
        )

    if bool(config["rerank"]["enabled"]):
        rerank_model = str(config["rerank"]["model_name"])
        rerank_top_k = int(config["rerank"]["top_k"])
        items = _rerank(query, items, rerank_model, rerank_top_k)

    print(json.dumps({"query": query, "results": items}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
