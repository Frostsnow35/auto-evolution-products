"""Q&A over indexed files using LLM."""
from __future__ import annotations
import json
import urllib.request

from . import config as cfg
from .embedder import get_embedder
from . import store


def _call_ollama_chat(prompt: str, model: str, url: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


def _call_api_chat(prompt: str, model: str, api_key: str, base_url: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def ask(question: str, top_k: int = 5) -> tuple[str, list[dict]]:
    """Answer a question using indexed files as context."""
    config = cfg.load_config()
    db_path = config["db_path"]

    embedder = get_embedder(config)
    q_embedding = embedder.embed([question])[0]
    results = store.search(db_path, q_embedding, top_k=top_k)

    if not results:
        return "No relevant files found in the index.", []

    # Build context
    context_parts = []
    seen_files = set()
    for r in results:
        fp = r["file_path"]
        seen_files.add(fp)
        context_parts.append(f"[File: {fp}]\n{r['chunk']}")

    context = "\n\n---\n\n".join(context_parts)
    prompt = (
        f"You are a file system assistant. Answer the user's question based ONLY on the file contents below.\n"
        f"If the answer isn't in the files, say so.\n\n"
        f"=== FILE CONTENTS ===\n{context}\n\n"
        f"=== QUESTION ===\n{question}\n\n"
        f"=== ANSWER ==="
    )

    if config.get("mode") == "api" and config.get("api_key"):
        answer = _call_api_chat(
            prompt,
            model=config.get("api_llm_model", "gpt-4o-mini"),
            api_key=config["api_key"],
            base_url=config.get("api_base", "https://api.openai.com/v1"),
        )
    else:
        answer = _call_ollama_chat(
            prompt,
            model=config.get("ollama_llm", "llama3"),
            url=config.get("ollama_url", "http://localhost:11434"),
        )

    return answer, results
