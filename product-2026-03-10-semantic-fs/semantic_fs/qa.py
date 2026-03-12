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
    raw_results = store.search(db_path, q_embedding, top_k=max(top_k * 3, top_k))

    if not raw_results:
        return "No relevant files found in the index.", []

    # Deduplicate by file, keep best chunk first.
    best_by_file: dict[str, dict] = {}
    for r in raw_results:
        fp = r["file_path"]
        if fp not in best_by_file or r["score"] > best_by_file[fp]["score"]:
            best_by_file[fp] = r

    results = sorted(best_by_file.values(), key=lambda x: -x["score"])[:top_k]

    context_parts = []
    for i, r in enumerate(results, start=1):
        context_parts.append(
            f"[Source {i}]\n"
            f"File: {r['file_path']}\n"
            f"Score: {r['score']}\n"
            f"Content:\n{r['chunk']}"
        )

    context = "\n\n---\n\n".join(context_parts)
    prompt = (
        "You are a precise file-system QA assistant. "
        "Answer using ONLY the retrieved source content below. "
        "Prefer concrete facts over guesses. "
        "If the sources are insufficient or only weakly related, explicitly say the answer is uncertain.\n\n"
        "Rules:\n"
        "1. Do not invent projects, facts, or summaries not supported by the sources.\n"
        "2. If multiple candidate projects appear, list them briefly.\n"
        "3. Keep the answer concise and directly responsive to the question.\n"
        "4. When useful, mention the most relevant source files by path.\n\n"
        f"=== QUESTION ===\n{question}\n\n"
        f"=== RETRIEVED SOURCES ===\n{context}\n\n"
        "=== ANSWER ==="
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
            model=config.get("ollama_llm", "llama3.2:1b"),
            url=config.get("ollama_url", "http://localhost:11434"),
        )

    return answer, results
