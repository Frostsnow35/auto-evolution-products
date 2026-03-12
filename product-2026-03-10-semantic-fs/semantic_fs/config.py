"""Configuration management for Semantic FS."""
import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "mode": "local",  # "local" or "api"
    "ollama_model": "nomic-embed-text",
    "ollama_llm": "llama3.2:1b",
    "ollama_url": "http://localhost:11434",
    "api_key": "",
    "api_base": "https://api.openai.com/v1",
    "api_embed_model": "text-embedding-3-small",
    "api_llm_model": "gpt-4o-mini",
    "db_path": "~/.semantic-fs/db",
    "index_paths": ["~/"],
    "exclude_patterns": [
        ".git", "__pycache__", "node_modules", ".npm", ".cache",
        "*.pyc", "*.o", "*.so", "*.bin", "*.jpg", "*.png",
        "*.mp4", "*.mp3", "*.zip", "*.tar.gz",
    ],
    "max_file_size_mb": 10,
    "chunk_size": 500,
    "chunk_overlap": 50,
}

CONFIG_PATH = Path("~/.semantic-fs/config.json").expanduser()


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        return {**DEFAULT_CONFIG, **data}
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get(key: str):
    return load_config().get(key)


def set_value(key: str, value: str):
    config = load_config()
    # Type coercion for known int/list keys
    config[key] = value
    save_config(config)
