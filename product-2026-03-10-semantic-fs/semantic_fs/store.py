"""ChromaDB-backed vector store for Semantic FS."""
from __future__ import annotations
from pathlib import Path
import hashlib


def _get_client(db_path: str):
    import chromadb
    path = str(Path(db_path).expanduser())
    Path(path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=path)


def _collection(client):
    return client.get_or_create_collection(
        name="semantic_fs",
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    db_path: str,
    file_path: str,
    chunks: list[str],
    embeddings: list[list[float]],
    mtime: float | None = None,
):
    """Store chunks + embeddings for a file (replaces old entries)."""
    client = _get_client(db_path)
    col = _collection(client)

    # Delete old chunks for this file
    try:
        col.delete(where={"file_path": file_path})
    except Exception:
        pass

    if not chunks:
        return

    ids = [
        hashlib.md5(f"{file_path}::{i}".encode()).hexdigest()
        for i in range(len(chunks))
    ]
    metadatas = []
    for i in range(len(chunks)):
        meta = {"file_path": file_path, "chunk_idx": i}
        if mtime is not None:
            meta["mtime"] = mtime
        metadatas.append(meta)
    col.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )


def search(db_path: str, query_embedding: list[float], top_k: int = 10) -> list[dict]:
    """Return top-k results with file_path, chunk text, distance."""
    client = _get_client(db_path)
    col = _collection(client)

    try:
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, col.count()),
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    out = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append({
            "file_path": meta["file_path"],
            "chunk": doc,
            "score": round(1 - dist, 4),  # cosine similarity
        })
    return out


def get_indexed_files(db_path: str) -> set[str]:
    return set(get_indexed_file_mtimes(db_path).keys())


def get_indexed_file_mtimes(db_path: str) -> dict[str, float | None]:
    client = _get_client(db_path)
    col = _collection(client)
    try:
        all_meta = col.get(include=["metadatas"])["metadatas"]
    except Exception:
        return {}

    out: dict[str, float | None] = {}
    for meta in all_meta:
        if not meta:
            continue
        file_path = meta.get("file_path")
        if not file_path:
            continue
        out.setdefault(file_path, meta.get("mtime"))
    return out


def prune_missing_files(db_path: str, existing_paths: set[str]) -> int:
    """Remove indexed entries for files that no longer exist on disk."""
    removed = 0
    for file_path in get_indexed_files(db_path):
        if file_path not in existing_paths:
            delete_file(db_path, file_path)
            removed += 1
    return removed


def delete_file(db_path: str, file_path: str):
    client = _get_client(db_path)
    col = _collection(client)
    try:
        col.delete(where={"file_path": file_path})
    except Exception:
        pass


def count(db_path: str) -> int:
    client = _get_client(db_path)
    col = _collection(client)
    try:
        return col.count()
    except Exception:
        return 0
