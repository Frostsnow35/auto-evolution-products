"""Indexer: walk directories, read files, embed, store."""
from __future__ import annotations
import fnmatch
import time
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


def _index_single_file(
    file_path: Path,
    *,
    db_path: str,
    max_mb: float,
    chunk_size: int,
    chunk_overlap: int,
    exclude: list[str],
    indexed_mtimes: dict[str, float | None],
    embedder,
    force: bool = False,
) -> bool:
    if _is_excluded(file_path, exclude) or not can_read(file_path, max_mb):
        return False

    fp_str = str(file_path)
    current_mtime = file_path.stat().st_mtime
    if not force and fp_str in indexed_mtimes and indexed_mtimes[fp_str] == current_mtime:
        return False

    text = read_file(file_path)
    if not text.strip():
        return False

    chunks = chunk_text(text, chunk_size, chunk_overlap)
    if not chunks:
        return False

    try:
        embeddings = embedder.embed(chunks)
    except Exception:
        return False

    store.upsert_chunks(db_path, fp_str, chunks, embeddings, mtime=current_mtime)
    indexed_mtimes[fp_str] = current_mtime
    return True


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
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")

    # Collect candidate files
    if root_path.is_file():
        candidates = [root_path] if can_read(root_path, max_mb) and not _is_excluded(root_path, exclude) else []
        should_prune = False
    else:
        candidates = []
        for p in root_path.rglob("*"):
            if _is_excluded(p, exclude):
                continue
            if can_read(p, max_mb):
                candidates.append(p)
        should_prune = True

    total = len(candidates)
    candidate_paths = {str(p) for p in candidates}
    if should_prune:
        store.prune_missing_files(db_path, candidate_paths, scope_root=str(root_path))
    indexed_mtimes = store.get_indexed_file_mtimes(db_path)

    for i, file_path in enumerate(candidates):
        fp_str = str(file_path)
        if progress_cb:
            progress_cb(fp_str, i + 1, total)
        _index_single_file(
            file_path,
            db_path=db_path,
            max_mb=max_mb,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            exclude=exclude,
            indexed_mtimes=indexed_mtimes,
            embedder=embedder,
            force=force,
        )

    return total


def index_file(path: str, force: bool = False) -> bool:
    """Index one file if it is new or changed."""
    config = cfg.load_config()
    db_path = config["db_path"]
    max_mb = config.get("max_file_size_mb", 10)
    chunk_size = config.get("chunk_size", 500)
    chunk_overlap = config.get("chunk_overlap", 50)
    exclude = config.get("exclude_patterns", [])
    embedder = get_embedder(config)
    indexed_mtimes = store.get_indexed_file_mtimes(db_path)
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        store.delete_file(db_path, str(file_path))
        return False
    return _index_single_file(
        file_path,
        db_path=db_path,
        max_mb=max_mb,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        exclude=exclude,
        indexed_mtimes=indexed_mtimes,
        embedder=embedder,
        force=force,
    )


def watch_path(root: str, recursive: bool = True, settle_seconds: float = 1.0):
    """Watch a path and incrementally re-index changed files."""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Watch path must be a directory: {root_path}")

    class Handler(FileSystemEventHandler):
        def __init__(self):
            self.last_seen: dict[str, float] = {}

        def _should_handle(self, path: str) -> bool:
            now = time.time()
            last = self.last_seen.get(path, 0)
            if now - last < settle_seconds:
                return False
            self.last_seen[path] = now
            return True

        def _handle(self, path: str):
            if self._should_handle(path):
                index_file(path)

        def on_created(self, event):
            if not event.is_directory:
                self._handle(event.src_path)

        def on_modified(self, event):
            if not event.is_directory:
                self._handle(event.src_path)

        def on_deleted(self, event):
            if not event.is_directory:
                self._handle(event.src_path)

        def on_moved(self, event):
            if not event.is_directory:
                self._handle(event.src_path)
                self._handle(event.dest_path)

    observer = Observer()
    observer.schedule(Handler(), str(root_path), recursive=recursive)
    observer.start()
    return observer
