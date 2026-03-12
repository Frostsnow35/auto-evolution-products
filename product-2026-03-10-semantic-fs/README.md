# Semantic FS — AI-Powered Semantic File System for Linux

> Find files by what they *mean*, not where they *are*.

## What Is This?

Semantic FS is a Linux CLI tool that indexes your home directory using AI embeddings and lets you search files by natural language queries — no more remembering folder structures or filenames.

```bash
# Instead of: find ~/Documents -name "*.pdf" | xargs grep -l "budget"
# Just type:
sfs search "budget report from last quarter"

# Or ask questions:
sfs ask "what did I write about the project timeline?"
```

## Features (v1)

- 🔍 **Semantic Search** — find files by meaning, not keywords
- 💬 **Q&A Mode** — ask questions, get answers sourced from your files
- 🔒 **Privacy First** — local mode (Ollama) or API mode (configurable)
- 📁 **Deep Indexing** — text files, markdown, PDFs, code, notes
- ⚡ **Incremental Updates** — skips unchanged files by mtime, prunes stale entries for deleted files, and can watch directories for background re-indexing

## Architecture

```
~/ (home directory)
    ↓ file watcher (watchdog)
[Indexer] → chunks text → [Embedder] → stores in [ChromaDB / local vector store]
                                              ↓
                                    [sfs CLI] ← user query
                                              ↓
                                    embed query → cosine similarity search
                                              ↓
                                    return ranked results / LLM Q&A
```

## Tech Stack

- **Language:** Python 3.10+
- **Embeddings:** `sentence-transformers` (local) or OpenAI/Copilot API
- **Vector Store:** ChromaDB (local, no server needed)
- **LLM Q&A:** Ollama (local) or API
- **File Watching:** `watchdog`
- **CLI:** `click` + `rich`

## Installation

```bash
cd semantic-fs
pip install -e .

# Initialize and index your home directory
sfs init
sfs index ~/
```

## Usage

```bash
# Search
sfs search "meeting notes with Alice"
sfs search "python script that processes CSV files"

# Q&A
sfs ask "what projects am I currently working on?"
sfs ask "summarize my notes about machine learning"

# Status
sfs status

# Re-index a specific directory
sfs index ~/Documents

# Watch a directory and incrementally re-index changed files
sfs watch ~/Documents
```

## Privacy Modes

```bash
# Local mode (default) — uses Ollama, fully offline
sfs config set mode local
sfs config set ollama_model nomic-embed-text

# API mode — faster, requires API key
sfs config set mode api
sfs config set api_key YOUR_KEY
```

## Roadmap

- **v1** ✅ Index + semantic search + Q&A
- **v2** Project-aware grouping, auto-tagging, timeline view
- **v3** Speed optimization, background daemon, multi-threaded indexing

---

*Built by 南小鸟 🐦 | AI × OS Series | 2026-03-10*
