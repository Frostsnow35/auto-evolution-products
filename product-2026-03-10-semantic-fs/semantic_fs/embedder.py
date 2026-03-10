"""Embedding backend — local (Ollama) or API."""
from __future__ import annotations
from typing import Protocol
import json
import urllib.request


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    """Use Ollama's local embedding endpoint."""

    def __init__(self, model: str = "nomic-embed-text", url: str = "http://localhost:11434"):
        self.model = model
        self.url = url.rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            payload = json.dumps({"model": self.model, "prompt": text}).encode()
            req = urllib.request.Request(
                f"{self.url}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            results.append(data["embedding"])
        return results

    def is_available(self) -> bool:
        try:
            urllib.request.urlopen(f"{self.url}/api/tags", timeout=3)
            return True
        except Exception:
            return False


class APIEmbedder:
    """Use OpenAI-compatible API for embeddings."""

    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        import urllib.request, json
        payload = json.dumps({"model": self.model, "input": texts}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return [item["embedding"] for item in data["data"]]


def get_embedder(config: dict) -> Embedder:
    if config.get("mode") == "api" and config.get("api_key"):
        return APIEmbedder(
            api_key=config["api_key"],
            base_url=config.get("api_base", "https://api.openai.com/v1"),
            model=config.get("api_embed_model", "text-embedding-3-small"),
        )
    return OllamaEmbedder(
        model=config.get("ollama_model", "nomic-embed-text"),
        url=config.get("ollama_url", "http://localhost:11434"),
    )
