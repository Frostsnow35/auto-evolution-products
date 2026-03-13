"""Lightweight project-oriented semantic view built on top of search results."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from . import config as cfg
from .embedder import get_embedder
from . import store

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "about", "your",
    "have", "will", "would", "could", "should", "than", "then", "them", "they", "their",
    "what", "when", "where", "which", "while", "were", "been", "being", "also", "just",
    "todo", "done", "file", "files", "note", "notes", "project", "projects", "semantic",
    "system", "using", "used", "user", "users", "work", "works", "working", "path", "paths",
    "index", "search", "view", "overview", "document", "documents", "data", "text",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())


def _extract_keywords(results: list[dict], limit: int = 8) -> list[str]:
    counts: Counter[str] = Counter()
    for result in results:
        counts.update(token for token in _tokenize(result.get("chunk", "")) if token not in STOPWORDS)
        path = Path(result["file_path"])
        counts.update(
            token
            for token in _tokenize(" ".join(path.parts[-3:]))
            if token not in STOPWORDS
        )
    return [word for word, _ in counts.most_common(limit)]


def _classify_risks(results: list[dict]) -> list[str]:
    risks: list[str] = []
    joined = "\n".join(result.get("chunk", "").lower() for result in results)
    if any(token in joined for token in ["todo", "fixme", "hack", "later", "pending"]):
        risks.append("检索结果里包含 TODO / FIXME / pending 等信号，说明项目可能仍有未完成事项。")
    if len({result["file_path"] for result in results}) <= 1:
        risks.append("相关结果文件数偏少，项目视图可能受索引覆盖不足或查询词过窄影响。")
    if not risks:
        risks.append("当前结果未发现明确阻塞信号，但该视图仍基于启发式聚合，不应替代人工判断。")
    return risks


def build_project_view(query: str, top_k: int = 8) -> dict:
    """Return a lightweight project summary from semantic search results."""
    config = cfg.load_config()
    embedder = get_embedder(config)
    query_embedding = embedder.embed([query])[0]
    raw_results = store.search(config["db_path"], query_embedding, top_k=max(top_k * 3, top_k))
    if not raw_results:
        return {
            "query": query,
            "summary": "未找到相关索引结果。请先运行 sfs index，或尝试更具体的项目关键词。",
            "key_files": [],
            "recent_changes": [],
            "risks": ["当前索引中没有可用于项目视图的相关内容。"],
            "keywords": [],
        }

    best_by_file: dict[str, dict] = {}
    for result in raw_results:
        fp = result["file_path"]
        if fp not in best_by_file or result["score"] > best_by_file[fp]["score"]:
            best_by_file[fp] = result

    indexed_mtimes = store.get_indexed_file_mtimes(config["db_path"])
    deduped = sorted(best_by_file.values(), key=lambda item: -float(item["score"]))[:top_k]

    key_files = []
    for result in deduped[:5]:
        fp = result["file_path"]
        key_files.append({
            "file_path": fp,
            "score": result["score"],
            "preview": result.get("chunk", "")[:140].replace("\n", " "),
        })

    recent_changes = []
    for fp, mtime in sorted(indexed_mtimes.items(), key=lambda item: item[1] or 0, reverse=True):
        if fp in best_by_file:
            recent_changes.append({
                "file_path": fp,
                "updated_at": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "unknown",
                "score": best_by_file[fp]["score"],
            })
        if len(recent_changes) >= 5:
            break

    keywords = _extract_keywords(deduped)
    summary_parts = []
    summary_parts.append(f"围绕“{query}”共聚合到 {len(deduped)} 个高相关文件。")
    if keywords:
        summary_parts.append(f"高频主题词包括：{', '.join(keywords[:5])}。")
    if key_files:
        top_path = Path(key_files[0]["file_path"]).name
        summary_parts.append(f"当前最关键的候选文件是：{top_path}。")

    return {
        "query": query,
        "summary": " ".join(summary_parts),
        "key_files": key_files,
        "recent_changes": recent_changes,
        "risks": _classify_risks(deduped),
        "keywords": keywords,
    }
