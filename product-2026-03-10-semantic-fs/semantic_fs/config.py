"""Configuration management for Semantic FS."""
import json
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

_INT_KEYS = {"chunk_size", "chunk_overlap"}
_FLOAT_KEYS = {"max_file_size_mb"}
_LIST_KEYS = {"index_paths", "exclude_patterns"}

CONFIG_PATH = Path("~/.semantic-fs/config.json").expanduser()


def _coerce_config_value(key: str, value):
    if key in _INT_KEYS:
        if isinstance(value, str):
            value = value.strip()
        return int(value)
    if key in _FLOAT_KEYS:
        if isinstance(value, str):
            value = value.strip()
        return float(value)
    if key in _LIST_KEYS:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError(f"{key} must be a JSON list")
                return parsed
            return [item.strip() for item in stripped.split(",") if item.strip()]
        raise ValueError(f"Unsupported value type for {key}: {type(value).__name__}")
    return value


def _normalize_config(config: dict) -> dict:
    normalized = {**DEFAULT_CONFIG, **config}
    for key in (*_INT_KEYS, *_FLOAT_KEYS, *_LIST_KEYS):
        if key in normalized:
            normalized[key] = _coerce_config_value(key, normalized[key])
    return normalized


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        return _normalize_config(data)
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get(key: str):
    return load_config().get(key)


def set_value(key: str, value: str):
    config = load_config()
    config[key] = _coerce_config_value(key, value)
    save_config(config)
