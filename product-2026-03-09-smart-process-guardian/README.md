# Smart Process Guardian 🛡️

**AI-powered Linux process monitor with anomaly detection and LLM diagnostics**

> Day 2 of [auto-evolution-products](https://github.com/Frostsnow35/auto-evolution-products) — AI × OS intersection, one product every 48 hours.

---

## What it does

Smart Process Guardian continuously watches your running processes and:

1. **Detects anomalies** — high CPU, memory leaks, zombie processes, runaway threads, FD exhaustion
2. **Generates human-readable reports** — clean terminal output with per-process flags
3. **AI-powered diagnosis** — sends anomaly data to an LLM (OpenAI-compatible) and gets back root-cause analysis + shell commands to fix issues
4. **Watch mode** — polls on a configurable interval with live screen refresh

## Why AI × OS?

Traditional process monitors show you *numbers*. This tool interprets them. Instead of staring at `top` and guessing why your system is slow, you get:

```
🤖 AI ANALYSIS:
──────────────────────────────────────────────────
Your system is under moderate memory pressure (82% used). The main concern
is process 'node' (PID 18234) which has been running for 4h and consumed
3.2 GB RAM — likely a memory leak in a long-running Node.js service.

Recommendations:
1. Check for memory leak: node --inspect PID 18234
2. Review heap usage: kill -USR2 18234 (triggers heapdump if configured)
3. Restart service if heap keeps growing: systemctl restart my-node-app
4. Zombie PID 9901 (parent: bash 9900) — run: kill -9 9901 or reap with: wait 9901
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Quick scan (no AI if OPENAI_API_KEY not set)
python process_guardian.py

# Watch mode — rescan every 30 seconds
python process_guardian.py --watch 30

# Inspect a specific PID
python process_guardian.py --pid 1234

# Analyze top 10 processes only
python process_guardian.py --top 10

# Report only, skip AI
python process_guardian.py --no-ai

# Save JSON report
python process_guardian.py --json

# Custom thresholds
python process_guardian.py --threshold-cpu 60 --threshold-mem 1024

# Use a different model (e.g. local ollama)
OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama \
  python process_guardian.py --model llama3
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (or any OpenAI-compatible key) |
| `OPENAI_BASE_URL` | Custom API base URL (for local models, Azure, etc.) |
| `GUARDIAN_API_KEY` | Alternative key name (same as `OPENAI_API_KEY`) |

## Anomaly Detection Rules

| Anomaly | Default Threshold |
|---|---|
| High CPU | > 80% |
| High Memory | > 2048 MB RSS |
| High Memory % | > 15% of total RAM |
| High Threads | > 200 threads |
| High File Descriptors | > 1000 open FDs |
| Zombie Process | Any zombie status |

All thresholds configurable via CLI flags.

## Sample Output

```
╔══════════════════════════════════════════════════╗
║        Smart Process Guardian — Scan Report      ║
╚══════════════════════════════════════════════════╝
  Time       : 2026-03-09T02:00:15.423891
  CPU Usage  : 34.2%
  Memory     : 67.8%   Swap: 12.3%
  Load Avg   : 1.42 / 1.18 / 0.97
  Processes  : 312   Zombies: 1

⚠️  ANOMALOUS PROCESSES:
──────────────────────────────────────────────────
  PID  18234  node                  sleeping
    CMD: node /usr/lib/code-server/out/node/entry.js
    CPU: 0.0%  MEM: 3218MB  Threads: 28
    ▶ HIGH_MEM: 3218 MB RSS

  PID   9901  bash                  zombie
    CMD: bash
    CPU: 0.0%  MEM: 0MB  Threads: 1
    ▶ ZOMBIE: process is a zombie (parent not reaping)
```

## Architecture

```
process_guardian.py
├── collect_system_snapshot()   # psutil-based process collection
├── detect_anomalies()          # rule-based threshold checks
├── format_report()             # terminal-friendly ASCII report
├── build_ai_prompt()           # JSON context → LLM prompt
└── get_ai_analysis()           # OpenAI-compatible API call
```

## Works with Local Models

Point it at any OpenAI-compatible endpoint:

```bash
# Ollama
OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama \
  python process_guardian.py --model llama3.2

# LM Studio
OPENAI_BASE_URL=http://localhost:1234/v1 OPENAI_API_KEY=lm-studio \
  python process_guardian.py --model mistral-7b
```

## License

MIT
