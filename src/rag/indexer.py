#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库写入接口（L3 沉淀知识）
负责将 Agent 研究完成后沉淀的经验写入向量库与关键词索引，
供后续检索复用，实现 Agent 自学习闭环。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _load_config() -> Dict[str, Any]:
    """加载 RAG 配置"""
    config_path = Path(__file__).resolve().parent / "config" / "rag_config.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def _chunk_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    """按最大长度切分文本，保留重叠（与 prepare_chunks.py 一致）"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks


def add_knowledge(text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    将一条沉淀经验写入知识库（L3 沉淀知识）。

    Args:
        text: 要写入的知识文本（自动分块）
        metadata: 附加元数据，建议至少包含 {query}

    Returns:
        是否写入成功
    """
    try:
        config = _load_config()
        meta: Dict[str, Any] = dict(metadata or {})
        meta.setdefault("source", "agent_memory")
        meta.setdefault("layer", "L3")
        meta.setdefault("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        meta.setdefault("doc_id", "agent_memory")
        meta.setdefault("title", meta.get("query", "agent_memory"))

        base_dir = Path(__file__).resolve().parent

        # 1. 分块
        chunking = config.get("chunking", {})
        max_chars = int(chunking.get("max_chars", 800))
        overlap_chars = int(chunking.get("overlap_chars", 80))
        chunks = _chunk_text(text, max_chars, overlap_chars)
        if not chunks:
            logger.warning("add_knowledge: 文本为空，跳过")
            return False

        now_ms = int(time.time() * 1000)
        records: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            records.append({
                "chunk_id": f"agent_memory::{now_ms}::{i}",
                "doc_id": meta["doc_id"],
                "title": meta["title"],
                "text": chunk,
                "source_path": meta.get("source_path", "agent_memory"),
                "source": meta.get("source", "agent_memory"),
                "layer": meta.get("layer", "L3"),
                "created_at": meta.get("created_at", ""),
                "query": meta.get("query", ""),
            })

        # 2. 追加到关键词索引 chunks.jsonl
        chunks_dir = base_dir / config["data"]["chunks_dir"]
        chunks_path = chunks_dir / "chunks.jsonl"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        with chunks_path.open("a", encoding="utf-8") as handle:
            for rec in records:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")

        # 3. 尝试写入向量库（失败不阻塞关键词检索）
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            chroma_dir = base_dir / config["chroma"]["persist_dir"]
            collection_name = str(config["chroma"]["collection"])
            client = chromadb.PersistentClient(path=str(chroma_dir))
            collection = client.get_or_create_collection(name=collection_name)

            model_name = str(config["embedding"]["model_name"])
            local_only = bool(config.get("hf", {}).get("local_files_only", False))
            embedder = SentenceTransformer(model_name, local_files_only=local_only)

            ids = [r["chunk_id"] for r in records]
            documents = [r["text"] for r in records]
            metadatas = [{k: v for k, v in r.items() if k != "text"} for r in records]
            embeddings = embedder.encode(documents, normalize_embeddings=True).tolist()
            collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
            logger.info("add_knowledge: 已写入 %d 块到向量库 (layer=L3)", len(records))
        except Exception as exc:
            logger.warning("向量库写入失败（仅保留关键词索引）: %s", exc)

        logger.info("add_knowledge: 已沉淀 %d 块知识到知识库", len(records))
        return True
    except Exception as exc:
        logger.exception("add_knowledge 失败: %s", exc)
        return False


def rebuild_simple_index() -> None:
    """重建轻量关键词索引（simple_index.json）"""
    try:
        config = _load_config()
        base_dir = Path(__file__).resolve().parent
        chunks_path = base_dir / config["data"]["chunks_dir"] / "chunks.jsonl"
        if not chunks_path.exists():
            return
        items: List[Dict[str, Any]] = []
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        index_dir = base_dir / config["index"]["index_dir"]
        index_path = index_dir / config["index"]["index_file"]
        index_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps({"version": "simple-v1", "chunks": items}, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("已重建轻量索引: %d 块", len(items))
    except Exception as exc:
        logger.exception("重建轻量索引失败: %s", exc)
