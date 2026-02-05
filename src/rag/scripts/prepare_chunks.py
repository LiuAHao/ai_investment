#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
清洗原始文档并切分为知识块
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


@dataclass
class RagConfig:
    raw_dir: Path
    clean_dir: Path
    chunks_dir: Path
    max_chars: int
    min_chars: int
    overlap_chars: int
    encoding: str
    allowed_exts: List[str]


def _load_config(config_path: Path) -> RagConfig:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    base_dir = config_path.parent.parent
    raw_dir = base_dir / data["data"]["raw_dir"]
    clean_dir = base_dir / data["data"]["clean_dir"]
    chunks_dir = base_dir / data["data"]["chunks_dir"]
    return RagConfig(
        raw_dir=raw_dir,
        clean_dir=clean_dir,
        chunks_dir=chunks_dir,
        max_chars=int(data["chunking"]["max_chars"]),
        min_chars=int(data["chunking"]["min_chars"]),
        overlap_chars=int(data["chunking"]["overlap_chars"]),
        encoding=str(data["io"]["encoding"]),
        allowed_exts=[str(x) for x in data["io"]["allowed_exts"]],
    )


def _iter_files(root: Path, allowed_exts: List[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in allowed_exts:
            yield path


def _basic_clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _split_by_headings(text: str) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, str]] = []
    current_title = "未命名"
    buffer: List[str] = []

    for line in text.split("\n"):
        if re.match(r"^#{1,6}\s+", line):
            if buffer:
                sections.append((current_title, "\n".join(buffer).strip()))
                buffer = []
            current_title = line.lstrip("#").strip()
        else:
            buffer.append(line)

    if buffer:
        sections.append((current_title, "\n".join(buffer).strip()))

    return sections


def _chunk_text(text: str, max_chars: int, overlap_chars: int) -> List[str]:
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


def _ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _write_clean_file(clean_dir: Path, rel_path: Path, text: str, encoding: str) -> Path:
    clean_path = clean_dir / rel_path
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    clean_path.write_text(text, encoding=encoding)
    return clean_path


def _build_chunks(
    file_path: Path,
    rel_path: Path,
    text: str,
    config: RagConfig,
) -> List[Dict[str, str]]:
    sections = _split_by_headings(text)
    chunks: List[Dict[str, str]] = []

    for index, (title, section_text) in enumerate(sections, start=1):
        section_text = section_text.strip()
        if not section_text:
            continue
        for chunk_index, chunk in enumerate(
            _chunk_text(section_text, config.max_chars, config.overlap_chars), start=1
        ):
            if len(chunk) < config.min_chars:
                continue
            chunk_id = f"{rel_path.as_posix()}::{index}.{chunk_index}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": rel_path.as_posix(),
                    "title": title,
                    "text": chunk,
                    "source_path": rel_path.as_posix(),
                }
            )

    return chunks


def main() -> None:
    config_path = Path(__file__).resolve().parents[1] / "config" / "rag_config.json"
    config = _load_config(config_path)
    _ensure_dirs([config.clean_dir, config.chunks_dir])

    all_chunks: List[Dict[str, str]] = []
    for file_path in _iter_files(config.raw_dir, config.allowed_exts):
        rel_path = file_path.relative_to(config.raw_dir)
        raw_text = file_path.read_text(encoding=config.encoding)
        clean_text = _basic_clean(raw_text)
        _write_clean_file(config.clean_dir, rel_path, clean_text, config.encoding)
        all_chunks.extend(_build_chunks(file_path, rel_path, clean_text, config))

    chunks_path = config.chunks_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding=config.encoding) as handle:
        for item in all_chunks:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"已生成知识块数量: {len(all_chunks)}")
    print(f"输出文件: {chunks_path}")


if __name__ == "__main__":
    main()
