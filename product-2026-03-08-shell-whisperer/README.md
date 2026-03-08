# 🐚 Shell Whisperer

> **Talk to your terminal in plain language — and learn shell as you go.**

AI-powered shell assistant that doesn't just give you commands — it teaches you *why* they work.

---

## What it does

You describe what you want in natural language. Shell Whisperer:

1. **Generates** the exact shell command
2. **Breaks down** every flag and argument with explanations
3. **Teaches** you the underlying concepts
4. **Tips** you off to related tricks
5. **Warns** you if something could be risky

This isn't just a command generator. It's a shell tutor that lives in your terminal.

---

## Example

```
🐦 What do you want to do? > find all log files larger than 10MB and delete them

📋 Command:
   find /var/log -name "*.log" -size +10M -delete

🔍 How it works:
   find /var/log
     └─ Start searching from the /var/log directory
   -name "*.log"
     └─ Match only files ending in .log (* is a wildcard)
   -size +10M
     └─ Only files larger than 10 megabytes (+ means "more than")
   -delete
     └─ Delete matched files in place (no trash, permanent!)

📖 Explanation:
   find is a powerful tool that walks directory trees looking for files.
   The -size flag uses suffixes: c=bytes, k=kilobytes, M=megabytes, G=gigabytes.
   -delete is more efficient than piping to xargs rm.

💡 Tip: Add -dry-run first to preview what would be deleted... actually, use
   -print instead of -delete first to see what matches before committing!

⚠️  Warning: -delete is permanent. There's no undo. Consider -print first.
```

---

## Setup

### Requirements

- Python 3.8+
- An OpenAI API key (or compatible local endpoint like Ollama)

### Install

```bash
pip install openai
```

### Configure

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Using a local model (Ollama)?**
```bash
export SW_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"
export SW_MODEL="llama3"
```

### Run

```bash
python3 shell_whisperer.py
```

---

## Usage

| Input | Action |
|-------|--------|
| Any natural language | Generate + explain a command |
| `run` | Execute the last suggested command |
| `quit` / `exit` | Exit |

---

## Why this exists

Most people learn shell commands by copy-pasting from Stack Overflow with no idea what they do. Shell Whisperer flips that — you still get the command you need, but you also get the *understanding*.

Over time, you stop needing the tool. That's the point.

---

## Design notes

- **AI×OS fusion**: Uses LLM reasoning to bridge natural language intent and OS-level operations
- **Educational first**: Every response prioritizes understanding over brevity
- **Safe by default**: Warns about destructive operations, suggests dry-run alternatives
- **Local model friendly**: Works with Ollama or any OpenAI-compatible endpoint

---

*Made by kotori 🐦 — product #1 of the auto-evolution series*
