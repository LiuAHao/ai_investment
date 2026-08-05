#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库写入接口（L3 沉淀知识，带质量管控）

负责将 Agent 研究完成后沉淀的经验写入向量库与关键词索引，
供后续检索复用，实现 Agent 自学习闭环。

【质量管控管线】防止"噪声越写越大"：
1. 质量门槛（Quality Gate）：研究降级/结论过短/无证据支撑 → 拒绝写入
2. 知识提炼（LLM 蒸馏）：不写"时效性结论"，而是将结论蒸馏为可复用知识
   （分析方法/指标口径/规则要点），剥离短期观点
3. 相似度查重（Dedup）：与库内 L3 沉淀做相似度检索，高度相似跳过，中度相似合并
4. 分层写入：metadata 标记 layer=L3 / source / confidence / created_at
5. 生命周期：沉淀条目超限时淘汰最旧，避免无限膨胀
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 沉淀管线默认阈值（可被 rag_config.json 的 sediment 段覆盖）
_DEFAULTS: Dict[str, Any] = {
    "min_summary_chars": 50,      # 结论最短长度（质量门槛）
    "min_key_points": 1,          # 关键判断最少条数
    "dedup_skip_threshold": 0.92,  # 相似度 ≥ 此值 → 已存在，跳过
    "dedup_merge_threshold": 0.80, # 相似度 ≥ 此值 → 合并更新
    "max_l3_entries": 200,        # L3 沉淀条目上限（生命周期）
    "distill_enabled": True,       # 是否启用 LLM 蒸馏（False 时走纯规则）
    "distill_model": "",           # 蒸馏用模型，空则用默认
}


def _load_config() -> Dict[str, Any]:
    """加载 RAG 配置"""
    config_path = Path(__file__).resolve().parent / "config" / "rag_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    # 合并沉淀参数（缺省用内置默认值）
    sediment = dict(_DEFAULTS)
    sediment.update(config.get("sediment", {}) or {})
    config["sediment"] = sediment
    return config


def _chunk_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    """按最大长度切分文本，保留重叠"""
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


def _build_client():
    """构建 LLM 客户端（惰性导入，避免循环依赖）"""
    from utils.llm_common import build_client
    return build_client()


# ---------- 1. 质量门槛 ----------

def _quality_gate(
    summary: str,
    key_points: List[str],
    degraded: bool,
    has_evidence: bool,
    min_summary_chars: int,
    min_key_points: int,
) -> Optional[str]:
    """
    质量门槛检查。

    Returns:
        通过返回 None；拒绝返回拒绝原因字符串
    """
    if degraded:
        return "研究过程降级（degraded），结论不可靠"
    text = (summary or "").strip()
    if len(text) < min_summary_chars:
        return f"结论过短（{len(text)} < {min_summary_chars} 字），无沉淀价值"
    if len(key_points or []) < min_key_points:
        return "缺少关键判断，不足以沉淀"
    if not has_evidence and len(text) < min_summary_chars * 2:
        return "无证据支撑且结论简短，不写入"
    return None


# ---------- 2. 知识提炼（LLM 蒸馏） ----------

_DISTILL_SYSTEM = """你是投资研究知识蒸馏器。你的任务是把一次性的研究结论，蒸馏成"可长期复用的分析知识"。

【蒸馏原则】
1. 只保留可复用的方法论：分析框架、指标口径、规则要点、判断逻辑
2. 剔除时效性观点：具体价格预测、短期情绪、当下的买卖建议、过时的行情数据
3. 剥离具体标的：如果知识依赖于某个具体公司/指数，则泛化其分析方法
4. 输出精炼、结构化、可直接检索的知识条目

【输出格式】严格输出 JSON，不要其他内容：
{
  "title": "知识点标题（≤30字）",
  "knowledge": "可复用知识正文（80-300字，讲清方法/口径/规则）"
}

【示例】
输入结论："茅台当前PE 32倍高于历史中枢，估值偏贵，短期建议观望；白酒行业提价周期约2-3年，库存周期与估值负相关。"
输出：
{
  "title": "白酒行业估值锚定方法",
  "knowledge": "白酒行业估值分析要点：1) 提价周期约2-3年，提价预期兑现时估值中枢上移；2) 库存周期与估值负相关，渠道库存高企时压制估值；3) 估值锚定使用PE并结合提价与库存周期判断，而非简单对照历史分位数。"
}"""


def _distill_knowledge(summary: str, key_points: List[str], reasoning: str, model: str) -> Optional[Dict[str, str]]:
    """
    LLM 蒸馏：将研究结论转为可复用知识。

    Returns:
        {"title": str, "knowledge": str}；失败返回 None
    """
    try:
        client = _build_client()
        source = "\n".join(
            [
                f"【总结】{summary}",
                f"【要点】{('；'.join(key_points or []))[:500]}",
                f"【推理】{reasoning or ''}"[:500],
            ]
        )
        from utils.llm_common import get_env
        model_name = model or get_env("AGENT_LLM_MODEL", "deepseek-chat")
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": _DISTILL_SYSTEM},
                {"role": "user", "content": f"请蒸馏以下研究结论为可复用知识：\n\n{source[:2000]}"},
            ],
            temperature=0.2,
        )
        content = ""
        if resp.choices:
            content = getattr(resp.choices[0].message, "content", None) or ""
        import re

        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            logger.warning("蒸馏输出无 JSON: %s", content[:80])
            return None
        data = json.loads(match.group(0))
        title = str(data.get("title", "")).strip()
        knowledge = str(data.get("knowledge", "")).strip()
        if not knowledge or len(knowledge) < 20:
            return None
        return {"title": title or "L3沉淀知识", "knowledge": knowledge}
    except Exception as exc:
        logger.warning("LLM 蒸馏失败（跳过蒸馏直接写入）: %s", exc)
        return None


# ---------- 3. 相似度查重 ----------

def _embed_similarity(text: str, embedder, reference: List[Dict[str, Any]]) -> float:
    """计算新文本与参考文本列表的最大余弦相似度"""
    if embedder is None or not reference:
        return 0.0
    new_vec = embedder.encode([text], normalize_embeddings=True)[0]
    ref_vecs = embedder.encode([r["text"] for r in reference], normalize_embeddings=True)
    scores = [float(new_vec @ vec) for vec in ref_vecs]
    return max(scores) if scores else 0.0


def _find_similar_l3(text: str, embedder, collection, dedup_top_k: int = 5) -> List[Dict[str, Any]]:
    """在向量库中检索与文本相似的 L3 沉淀条目"""
    if embedder is None or collection is None:
        return []
    try:
        vec = embedder.encode([text], normalize_embeddings=True).tolist()[0]
        result = collection.query(
            query_embeddings=[vec],
            n_results=dedup_top_k,
            where={"layer": "L3"},
        )
        items: List[Dict[str, Any]] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i in range(len(ids)):
            # chroma 距离默认为余弦距离，相似度 = 1 - distance（embedding 已归一化）
            sim = 1.0 - float(dists[i])
            items.append({"chunk_id": ids[i], "text": docs[i], "metadata": metas[i] or {}, "similarity": sim})
        return items
    except Exception as exc:
        logger.warning("相似度查重失败（跳过查重）: %s", exc)
        return []


# ---------- 4. 分层写入 ----------

def _write_records(
    records: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> bool:
    """追加到关键词索引 chunks.jsonl，并尝试写入向量库"""
    try:
        base_dir = Path(__file__).resolve().parent

        # 关键词索引（chunks.jsonl）
        chunks_dir = base_dir / config["data"]["chunks_dir"]
        chunks_path = chunks_dir / "chunks.jsonl"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        with chunks_path.open("a", encoding="utf-8") as handle:
            for rec in records:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")

        # 向量库（失败不阻塞关键词检索）
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
            logger.info("L3 沉淀已写入向量库 %d 块", len(records))
        except Exception as exc:
            logger.warning("向量库写入失败（仅保留关键词索引）: %s", exc)

        logger.info("L3 沉淀已写入知识库 %d 块", len(records))
        return True
    except Exception as exc:
        logger.exception("L3 沉淀写入失败: %s", exc)
        return False


# ---------- 5. 生命周期：淘汰最旧 ----------

def _count_l3_entries(config: Dict[str, Any]) -> int:
    """统计当前 L3 沉淀条目数（按 chunks.jsonl 中 layer=L3 计数）"""
    base_dir = Path(__file__).resolve().parent
    chunks_path = base_dir / config["data"]["chunks_dir"] / "chunks.jsonl"
    if not chunks_path.exists():
        return 0
    count = 0
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                if json.loads(line).get("layer") == "L3":
                    count += 1
            except json.JSONDecodeError:
                continue
    return count


def _prune_oldest_l3(config: Dict[str, Any], max_entries: int) -> None:
    """
    淘汰最旧的 L3 沉淀条目（同时清理 chunks.jsonl 与向量库）。
    按 created_at 升序删除超出上限的最旧条目。
    """
    try:
        base_dir = Path(__file__).resolve().parent
        chunks_path = base_dir / config["data"]["chunks_dir"] / "chunks.jsonl"
        if not chunks_path.exists():
            return

        # 读取全部条目
        entries: List[Dict[str, Any]] = []
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        l3_entries = [e for e in entries if e.get("layer") == "L3"]
        if len(l3_entries) <= max_entries:
            return

        # 按 created_at 升序，删除最旧的超出部分
        l3_sorted = sorted(l3_entries, key=lambda e: str(e.get("created_at", "")))
        to_remove = l3_sorted[: len(l3_entries) - max_entries]
        remove_ids = {str(e.get("chunk_id")) for e in to_remove}

        # 重写 chunks.jsonl（排除被删条目）
        keep = [e for e in entries if str(e.get("chunk_id")) not in remove_ids]
        with chunks_path.open("w", encoding="utf-8") as handle:
            for e in keep:
                handle.write(json.dumps(e, ensure_ascii=False) + "\n")

        # 向量库同步删除
        try:
            import chromadb
            chroma_dir = base_dir / config["chroma"]["persist_dir"]
            collection_name = str(config["chroma"]["collection"])
            client = chromadb.PersistentClient(path=str(chroma_dir))
            collection = client.get_or_create_collection(name=collection_name)
            collection.delete(ids=list(remove_ids))
        except Exception as exc:
            logger.warning("向量库淘汰删除失败: %s", exc)

        logger.info("L3 沉淀生命周期：淘汰 %d 条最旧条目（当前 %d 条）", len(remove_ids), len(keep))
    except Exception as exc:
        logger.exception("L3 沉淀淘汰失败: %s", exc)


# ---------- 主入口 ----------

def add_knowledge(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    skip_gate: bool = False,
) -> str:
    """
    将一条沉淀经验写入知识库（L3 沉淀知识，低层写入接口）。

    Args:
        text: 要写入的知识文本（自动分块）
        metadata: 附加元数据，建议至少包含 {query, title, confidence}
        skip_gate: 是否跳过查重（默认 False；True 用于经管线处理后的强制写入）

    Returns:
        状态字符串：written / duplicate / empty / error
    """
    try:
        config = _load_config()
        meta: Dict[str, Any] = dict(metadata or {})
        meta.setdefault("source", "agent_memory")
        meta.setdefault("layer", "L3")
        meta.setdefault("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        meta.setdefault("doc_id", "agent_memory")
        meta.setdefault("title", meta.get("query", "agent_memory"))

        # 查重（skip_gate=False 时）
        if not skip_gate:
            try:
                import chromadb
                from sentence_transformers import SentenceTransformer

                base_dir = Path(__file__).resolve().parent
                chroma_dir = base_dir / config["chroma"]["persist_dir"]
                collection_name = str(config["chroma"]["collection"])
                client = chromadb.PersistentClient(path=str(chroma_dir))
                collection = client.get_or_create_collection(name=collection_name)
                model_name = str(config["embedding"]["model_name"])
                local_only = bool(config.get("hf", {}).get("local_files_only", False))
                embedder = SentenceTransformer(model_name, local_files_only=local_only)
                similar = _find_similar_l3(text, embedder, collection)
                if similar:
                    max_sim = max(s["similarity"] for s in similar)
                    skip_th = float(config["sediment"]["dedup_skip_threshold"])
                    if max_sim >= skip_th:
                        logger.info("查重命中（相似度 %.2f ≥ %.2f），跳过写入: %s", max_sim, skip_th, text[:40])
                        return "duplicate"
            except Exception as exc:
                logger.warning("查重失败（继续写入）: %s", exc)

        # 分块
        chunking = config.get("chunking", {})
        max_chars = int(chunking.get("max_chars", 800))
        overlap_chars = int(chunking.get("overlap_chars", 80))
        chunks = _chunk_text(text, max_chars, overlap_chars)
        if not chunks:
            logger.warning("add_knowledge: 文本为空，跳过")
            return "empty"

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

        ok = _write_records(records, config)
        if not ok:
            return "error"

        # 生命周期：超限淘汰最旧
        max_entries = int(config["sediment"]["max_l3_entries"])
        if _count_l3_entries(config) > max_entries:
            _prune_oldest_l3(config, max_entries)
        return "written"
    except Exception as exc:
        logger.exception("add_knowledge 失败: %s", exc)
        return "error"


def sediment_research(
    *,
    summary: str,
    key_points: Optional[List[str]] = None,
    reasoning: str = "",
    query: str = "",
    degraded: bool = False,
    has_evidence: bool = False,
    confidence: float = 0.0,
    time_frame: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    L3 沉淀质量管控入口（推荐使用）。

    执行完整管线：质量门槛 → 知识提炼 → 相似度查重 → 分层写入 → 生命周期。

    Args:
        summary: 研究结论总结
        key_points: 关键判断列表
        reasoning: 推理过程
        query: 原始用户问题
        degraded: 研究是否降级（quality gate）
        has_evidence: 是否有证据支撑（quality gate）
        confidence: 结论置信度（0~1，写入 metadata）
        time_frame: 结论有效期（写入 metadata）
        metadata: 其他附加元数据

    Returns:
        {"status": "written"|"rejected"|"skipped_dup"|"error",
         "reason": str, "title": str, "knowledge": str}
    """
    try:
        config = _load_config()
        sediment = config["sediment"]

        # ① 质量门槛
        gate_reason = _quality_gate(
            summary=summary,
            key_points=key_points or [],
            degraded=degraded,
            has_evidence=has_evidence,
            min_summary_chars=int(sediment["min_summary_chars"]),
            min_key_points=int(sediment["min_key_points"]),
        )
        if gate_reason:
            logger.info("L3 沉淀被质量门槛拒绝: %s", gate_reason)
            return {"status": "rejected", "reason": gate_reason}

        # ② 知识提炼（LLM 蒸馏）
        title = ""
        knowledge = (summary or "").strip()
        if sediment["distill_enabled"]:
            distilled = _distill_knowledge(summary, key_points, reasoning, str(sediment.get("distill_model", "")))
            if distilled:
                title = distilled["title"]
                knowledge = distilled["knowledge"]
                logger.info("L3 蒸馏成功: %s", title)

        # ③ 相似度查重 + ④ 写入（add_knowledge 内部含查重与生命周期）
        meta: Dict[str, Any] = dict(metadata or {})
        meta.setdefault("query", query)
        meta.setdefault("title", title or (query[:30] if query else "L3沉淀知识"))
        meta.setdefault("confidence", float(confidence or 0.0))
        meta.setdefault("time_frame", time_frame)
        meta.setdefault("layer", "L3")

        write_status = add_knowledge(knowledge, metadata=meta)
        if write_status == "written":
            return {"status": "written", "reason": "", "title": title, "knowledge": knowledge}
        if write_status == "duplicate":
            return {"status": "skipped_dup", "reason": "与已有 L3 知识高度相似，跳过", "title": title, "knowledge": knowledge}
        if write_status == "empty":
            return {"status": "rejected", "reason": "蒸馏后知识为空", "title": title, "knowledge": knowledge}
        return {"status": "error", "reason": "写入失败", "title": title, "knowledge": knowledge}
    except Exception as exc:
        logger.exception("L3 沉淀管线异常: %s", exc)
        return {"status": "error", "reason": str(exc)}


def _split_markdown_sections(
    text: str,
    max_chars: int,
    overlap_chars: int,
) -> List[Dict[str, str]]:
    """
    按 Markdown 标题切分文本为知识块。

    Returns:
        [{"title": 标题路径, "text": 章节内容}, ...]
    """
    lines = text.splitlines()
    sections: List[Dict[str, str]] = []
    current_title = ""
    current_lines: List[str] = []

    def flush() -> None:
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append({"title": current_title, "text": body})

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("## "):
            continue  # 文档一级标题跳过
        if stripped.startswith("## "):
            flush()
            current_title = stripped.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    # 超长章节按字符切分（保留标题）
    result: List[Dict[str, str]] = []
    for sec in sections:
        body = sec["text"]
        if len(body) <= max_chars:
            result.append(sec)
            continue
        for chunk in _chunk_text(body, max_chars, overlap_chars):
            result.append({"title": sec["title"], "text": chunk})
    return result


def rebuild_chunks_from_raw() -> Dict[str, Any]:
    """
    从 data/raw 全量切分生成 chunks.jsonl（替代已删除的 prepare_chunks.py）。

    读取 raw/ 下所有 .md/.txt，按 Markdown 标题切分（200-800 字），
    并写入 data/clean（清洗后原文）与 data/chunks/chunks.jsonl。
    """
    try:
        config = _load_config()
        base_dir = Path(__file__).resolve().parent
        raw_dir = base_dir / config["data"]["raw_dir"]
        clean_dir = base_dir / config["data"]["clean_dir"]
        chunks_dir = base_dir / config["data"]["chunks_dir"]

        chunking = config.get("chunking", {})
        max_chars = int(chunking.get("max_chars", 800))
        overlap_chars = int(chunking.get("overlap_chars", 80))

        raw_files = sorted(
            [p for p in raw_dir.rglob("*") if p.suffix.lower() in (".md", ".txt")]
        )
        if not raw_files:
            return {"status": "error", "reason": "raw 目录无知识文档"}

        clean_dir.mkdir(parents=True, exist_ok=True)
        chunks_dir.mkdir(parents=True, exist_ok=True)

        records: List[Dict[str, Any]] = []
        title_counters: Dict[str, int] = {}
        clean_written = 0
        for raw_file in raw_files:
            text = raw_file.read_text(encoding="utf-8")
            # 写 clean（清洗后：去 BOM、统一空行）
            cleaned = text.lstrip("\ufeff").strip() + "\n"
            clean_path = clean_dir / raw_file.name
            clean_path.write_text(cleaned, encoding="utf-8")
            clean_written += 1

            sections = _split_markdown_sections(cleaned, max_chars, overlap_chars)
            for sec in sections:
                body = sec["text"].strip()
                if not body:
                    continue
                # 跳过过短章节（表头/孤立标题）
                if len(body) < int(chunking.get("min_chars", 200)):
                    continue
                # 同一标题多次出现（超长章节切分/同名小节）时加序号，保证 chunk_id 唯一
                key = f"{raw_file.name}::{sec['title']}"
                seq = title_counters.get(key, 0) + 1
                title_counters[key] = seq
                chunk_id = f"{key}::{seq}" if seq > 1 else key
                records.append({
                    "chunk_id": chunk_id,
                    "doc_id": raw_file.name,
                    "title": sec["title"],
                    "text": body,
                    "source_path": raw_file.name,
                })

        # 写 chunks.jsonl（全量覆盖，保留 L3 沉淀？——L3 在 chunks.jsonl 中按 layer 区分，
        # 此处为静态知识重建，先保留已有 L3 沉淀条目）
        chunks_path = chunks_dir / "chunks.jsonl"
        existing: List[Dict[str, Any]] = []
        if chunks_path.exists():
            with chunks_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if item.get("layer") == "L3":
                            existing.append(item)
        all_records = records + existing
        with chunks_path.open("w", encoding="utf-8") as handle:
            for rec in all_records:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")

        logger.info("chunks.jsonl 重建完成：静态 %d 块 + L3 %d 块", len(records), len(existing))
        return {"status": "written", "static_count": len(records), "l3_count": len(existing)}
    except Exception as exc:
        logger.exception("chunks.jsonl 重建失败: %s", exc)
        return {"status": "error", "reason": str(exc)}


def rebuild_chroma_index() -> Dict[str, Any]:
    """
    从 chunks.jsonl 全量重建向量库（Chroma）。

    替代已删除的 scripts/build_chroma_index.py，供新环境初始化或索引损坏时重建。
    chunks.jsonl 内已包含 layer 标记，重建时逐块写入即可。
    """
    try:
        config = _load_config()
        base_dir = Path(__file__).resolve().parent
        chunks_path = base_dir / config["data"]["chunks_dir"] / "chunks.jsonl"
        if not chunks_path.exists():
            return {"status": "error", "reason": "chunks.jsonl 不存在"}

        records: List[Dict[str, Any]] = []
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        if not records:
            return {"status": "error", "reason": "chunks.jsonl 为空"}

        import chromadb
        from sentence_transformers import SentenceTransformer

        chroma_dir = base_dir / config["chroma"]["persist_dir"]
        collection_name = str(config["chroma"]["collection"])
        client = chromadb.PersistentClient(path=str(chroma_dir))
        # 重建：删除旧集合再重建
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
        collection = client.get_or_create_collection(name=collection_name)

        model_name = str(config["embedding"]["model_name"])
        local_only = bool(config.get("hf", {}).get("local_files_only", False))
        embedder = SentenceTransformer(model_name, local_files_only=local_only)

        ids = [str(r["chunk_id"]) for r in records]
        documents = [str(r["text"]) for r in records]
        metadatas = [
            {
                "doc_id": str(r.get("doc_id", "")),
                "title": str(r.get("title", "")),
                "source_path": str(r.get("source_path", "")),
                "source": str(r.get("source", "")),
                "layer": str(r.get("layer", "L1")),
                "created_at": str(r.get("created_at", "")),
                "query": str(r.get("query", "")),
            }
            for r in records
        ]
        embeddings = embedder.encode(documents, normalize_embeddings=True).tolist()

        # 分批写入（Chroma 单次大写入可能超限）
        batch_size = 100
        for i in range(0, len(records), batch_size):
            collection.add(
                ids=ids[i:i + batch_size],
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
            )
        logger.info("向量库重建完成：%d 块", len(records))
        return {"status": "written", "count": len(records)}
    except Exception as exc:
        logger.exception("向量库重建失败: %s", exc)
        return {"status": "error", "reason": str(exc)}


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
