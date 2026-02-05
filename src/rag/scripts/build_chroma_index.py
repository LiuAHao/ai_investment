#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
构建 Chroma 向量索引
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import chromadb
from sentence_transformers import SentenceTransformer


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


def _batch_iter(items: List[Dict[str, str]], batch_size: int) -> List[List[Dict[str, str]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    config_path = base_dir / "config" / "rag_config.json"
    config = _load_config(config_path)

    chunks_dir = base_dir / config["data"]["chunks_dir"]
    chunks_path = chunks_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"未找到知识块文件: {chunks_path}")

    chroma_dir = base_dir / config["chroma"]["persist_dir"]
    chroma_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection_name = str(config["chroma"]["collection"])

    if bool(config["chroma"]["reset"]):
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(name=collection_name)

    model_name = str(config["embedding"]["model_name"])
    local_only = bool(config.get("hf", {}).get("local_files_only", False))
    embedder = SentenceTransformer(model_name, local_files_only=local_only)

    chunks = _load_chunks(chunks_path)
    batch_size = int(config["chroma"]["batch_size"])

    for batch in _batch_iter(chunks, batch_size):
        ids = [item["chunk_id"] for item in batch]
        documents = [item["text"] for item in batch]
        metadatas = [
            {
                "doc_id": item.get("doc_id", ""),
                "title": item.get("title", ""),
                "source_path": item.get("source_path", ""),
            }
            for item in batch
        ]
        embeddings = embedder.encode(documents, normalize_embeddings=True).tolist()
        collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    print(f"已写入 Chroma: {collection_name}")
    print(f"索引条目数量: {len(chunks)}")


if __name__ == "__main__":
    main()
