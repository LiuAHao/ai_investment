#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RAG 知识库工具函数
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import chromadb
from sentence_transformers import CrossEncoder, SentenceTransformer

logger = logging.getLogger(__name__)


class RagKnowledgeBase:
    """RAG 知识库访问器（Chroma + Embedding + Rerank）"""

    def __init__(self) -> None:
        self._loaded = False
        self._config: Dict[str, Any] = {}
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self._embedder: Optional[SentenceTransformer] = None
        self._reranker: Optional[CrossEncoder] = None
        self._keyword_chunks: List[Dict[str, Any]] = []
        self._query_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def _load(self) -> None:
        if self._loaded:
            return
        base_dir = Path(__file__).resolve().parents[0]
        config_path = base_dir / "config" / "rag_config.json"
        self._config = json.loads(config_path.read_text(encoding="utf-8"))

        chroma_dir = base_dir / self._config["chroma"]["persist_dir"]
        collection_name = str(self._config["chroma"]["collection"])
        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        self._collection = self._client.get_or_create_collection(name=collection_name)

        # 向量模型加载失败时降级为纯关键词检索（不影响整体可用性）
        model_name = str(self._config["embedding"]["model_name"])
        local_only = bool(self._config.get("hf", {}).get("local_files_only", False))
        try:
            self._embedder = SentenceTransformer(model_name, local_files_only=local_only)
        except Exception as exc:
            logger.warning("embedding 模型加载失败，降级为纯关键词检索: %s", exc)
            self._embedder = None

        if self._embedder is not None and bool(self._config["rerank"]["enabled"]):
            try:
                rerank_model = str(self._config["rerank"]["model_name"])
                self._reranker = CrossEncoder(rerank_model, local_files_only=local_only)
            except Exception as exc:
                logger.warning("rerank 模型加载失败，跳过重排: %s", exc)
                self._reranker = None

        chunks_dir = base_dir / self._config["data"]["chunks_dir"]
        chunks_path = chunks_dir / "chunks.jsonl"
        if chunks_path.exists():
            self._keyword_chunks = self._load_chunks(chunks_path)

        self._loaded = True

    @staticmethod
    def _load_chunks(chunks_path: Path) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        return items

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower()
        return " ".join(text.split())

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        cleaned = "".join(ch if (ch.isalnum() or "\u4e00" <= ch <= "\u9fff") else " " for ch in text)
        tokens = [t for t in cleaned.split(" ") if t]
        return tokens if tokens else [ch for ch in cleaned if ch.strip()]

    def _keyword_rank(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if not self._keyword_chunks:
            return []
        normalized_query = self._normalize(query)
        query_tokens = self._tokenize(normalized_query)

        ranked: List[Tuple[int, Dict[str, Any]]] = []
        for chunk in self._keyword_chunks:
            text = self._normalize(str(chunk.get("text", "")))
            score = sum(text.count(token) for token in query_tokens)
            if score > 0:
                ranked.append((score, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        results: List[Dict[str, Any]] = []
        for score, chunk in ranked[:top_k]:
            results.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "text": chunk.get("text"),
                    "metadata": {
                        "doc_id": chunk.get("doc_id"),
                        "title": chunk.get("title"),
                        "source_path": chunk.get("source_path"),
                    },
                    "keyword_score": score,
                }
            )
        return results

    @staticmethod
    def _rrf_fuse(
        vector_items: Iterable[Dict[str, Any]],
        keyword_items: Iterable[Dict[str, Any]],
        rrf_k: int,
    ) -> List[Dict[str, Any]]:
        fused: Dict[str, Dict[str, Any]] = {}

        for rank, item in enumerate(vector_items, start=1):
            chunk_id = str(item.get("chunk_id"))
            if not chunk_id:
                continue
            entry = fused.get(chunk_id, dict(item))
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + 1.0 / (rrf_k + rank)
            fused[chunk_id] = entry

        for rank, item in enumerate(keyword_items, start=1):
            chunk_id = str(item.get("chunk_id"))
            if not chunk_id:
                continue
            entry = fused.get(chunk_id, dict(item))
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + 1.0 / (rrf_k + rank)
            fused[chunk_id] = entry

        return sorted(fused.values(), key=lambda x: x.get("rrf_score", 0.0), reverse=True)

    def _rerank(self, query: str, items: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        if not self._reranker or not items:
            return items
        pairs = [(query, str(item.get("text", ""))) for item in items]
        scores = self._reranker.predict(pairs)
        ranked: List[Tuple[float, Dict[str, Any]]] = []
        for score, item in zip(scores, items):
            updated = dict(item)
            updated["rerank_score"] = float(score)
            ranked.append((float(score), updated))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in ranked[:top_k]]

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        cache_conf = self._config.get("cache", {})
        if not cache_conf.get("enabled", False):
            return None
        ttl_seconds = int(cache_conf.get("ttl_seconds", 300))
        cached = self._query_cache.get(key)
        if not cached:
            return None
        ts, payload = cached
        if time.time() - ts > ttl_seconds:
            self._query_cache.pop(key, None)
            return None
        return payload

    def _set_cache(self, key: str, payload: Dict[str, Any]) -> None:
        cache_conf = self._config.get("cache", {})
        if not cache_conf.get("enabled", False):
            return
        max_size = int(cache_conf.get("max_size", 256))
        if len(self._query_cache) >= max_size:
            oldest_key = min(self._query_cache.items(), key=lambda item: item[1][0])[0]
            self._query_cache.pop(oldest_key, None)
        self._query_cache[key] = (time.time(), payload)

    def query(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        self._load()
        if not query:
            return {"query": query, "results": []}

        cache_key = f"{query}:{top_k}:{self._config.get('hybrid', {}).get('enabled', False)}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        config_top_k = int(self._config["query"]["top_k"])
        limit = int(top_k or config_top_k)
        hybrid_enabled = bool(self._config.get("hybrid", {}).get("enabled", False))
        vector_top_k = int(self._config.get("hybrid", {}).get("vector_top_k", limit))
        keyword_top_k = int(self._config.get("hybrid", {}).get("keyword_top_k", limit))
        rrf_k = int(self._config.get("hybrid", {}).get("rrf_k", 60))

        # embedding 不可用 → 纯关键词检索降级
        if self._embedder is None or self._collection is None:
            keyword_items = self._keyword_rank(query, keyword_top_k)
            items = keyword_items[:limit]
            if bool(self._config["rerank"]["enabled"]) and self._reranker is not None:
                try:
                    items = self._rerank_items(query, items, top_k=limit)
                except Exception:
                    pass
            return self._build_result(query, items, hybrid=False)

        query_embedding = self._embedder.encode([query], normalize_embeddings=True).tolist()[0]
        result = self._collection.query(query_embeddings=[query_embedding], n_results=vector_top_k)

        vector_items: List[Dict[str, Any]] = []
        for index in range(len(result.get("ids", [[]])[0])):
            vector_items.append(
                {
                    "chunk_id": result["ids"][0][index],
                    "text": result["documents"][0][index],
                    "metadata": result["metadatas"][0][index],
                    "distance": result["distances"][0][index],
                }
            )

        keyword_items = self._keyword_rank(query, keyword_top_k) if hybrid_enabled else []

        if hybrid_enabled:
            fused_items = self._rrf_fuse(vector_items, keyword_items, rrf_k)
            items = fused_items[:limit]
        else:
            items = vector_items[:limit]

        if bool(self._config["rerank"]["enabled"]):
            rerank_top_k = int(self._config["rerank"]["top_k"])
            min_candidates = int(self._config["rerank"].get("min_candidates", 2))
            if len(items) >= min_candidates and len(query) >= 2 and self._reranker is not None:
                items = self._rerank(query, items, rerank_top_k)

        return self._build_result(query, items, hybrid=hybrid_enabled, cache_key=cache_key)

    def _build_result(self, query: str, items: List[Dict[str, Any]], hybrid: bool = True, cache_key: str = "") -> Dict[str, Any]:
        """构建统一检索结果（含兜底判断）"""
        min_results = int(self._config.get("fallback", {}).get("min_results", 1))
        min_score = float(self._config.get("fallback", {}).get("min_score", 0.0))
        top_score = float(items[0].get("rrf_score", 0.0)) if items else 0.0
        fallback = (len(items) < min_results) or (top_score < min_score)

        citations: List[Dict[str, Any]] = []
        for item in items:
            meta = item.get("metadata") or {}
            citations.append(
                {
                    "title": meta.get("title") or "未命名",
                    "source": meta.get("source_path") or meta.get("doc_id") or "",
                }
            )

        payload = {
            "query": query,
            "results": items,
            "citations": citations,
            "fallback": fallback,
            "message": "知识库覆盖不足" if fallback else "",
            "mode": "keyword_only" if (self._embedder is None or self._collection is None) else ("hybrid" if hybrid else "vector"),
        }
        if cache_key:
            self._set_cache(cache_key, payload)
        return payload


_rag_singleton: Optional[RagKnowledgeBase] = None


def query_investment_knowledge(query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    """
    查询 RAG 知识库

    Args:
        query: 用户问题
        top_k: 返回条目数量（可选）

    Returns:
        结构化检索结果
    """
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = RagKnowledgeBase()
    try:
        return _rag_singleton.query(query, top_k=top_k)
    except Exception as exc:
        logger.exception("RAG 查询失败: %s", exc)
        return {"query": query, "results": [], "error": str(exc)}
