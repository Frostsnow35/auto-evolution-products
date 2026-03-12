"""Indexer: walk directories, read files, embed, store."""
from __future__ import annotations
import fnmatch
from pathlib import Path
from typing import Callable

from . import config as cfg
from .reader import can_read, read_file, chunk_text
from .embedder import get_embedder
from . import store


def _is_excluded(path: Path, patterns: list[str]) -> bool:
    for part in path.parts:
        for pat in patterns:
            if fnmatch.fnmatch(part, pat):
                return True
    return False


def index_path(
    root: str,
    progress_cb: Callable[[str, int, int], None] | None = None,
    force: bool = False,
):
    """Index all readable files under root."""
    config = cfg.load_config()
    db_path = config["db_path"]
    max_mb = config.get("max_file_size_mb", 10)
    chunk_size = config.get("chunk_size", 500)
    chunk_overlap = config.get("chunk_overlap", 50)
    exclude = config.get("exclude_patterns", [])

    embedder = get_embedder(config)
    root_path = Path(root).expanduser().resolve()

    # Collect candidate files
    candidates = []
    for p in root_path.rglob("*"):
        if _is_excluded(p, exclude):
            continue
        if can_read(p, max_mb):
            candidates.append(p)

    total = len(candidates)
    candidate_paths = {str(p) for p in candidates}
    store.prune_missing_files(db_path, candidate_paths)
    indexed_mtimes = store.get_indexed_file_mtimes(db_path)

    for i, file_path in enumerate(candidates):
        fp_str = str(file_path)
        if progress_cb:
            progress_cb(fp_str, i + 1, total)

        current_mtime = file_path.stat().st_mtime
        if not force and fp_str in indexed_mtimes and indexed_mtimes[fp_str] == current_mtime:
            continue

        text = read_file(file_path)
        if not text.strip():
            continue

        chunks = chunk_text(text, chunk_size, chunk_overlap)
        if not chunks:
            continue

        try:
            embeddings = embedder.embed(chunks)
        except Exception as e:
            # Skip files that fail to embed
            continue

        store.upsert_chunks(db_path, fp_str, chunks, embeddings, mtime=current_mtime)

    return total
