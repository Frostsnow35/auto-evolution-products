#!/usr/bin/env python3
"""
Shell Whisperer 🐚
AI-powered shell assistant that teaches you while it helps you.
Tell it what you want in plain language → get the command + explanation.

Author: kotori 🐦
"""

import os
import sys
import json
import subprocess
import shutil
from openai import OpenAI

# ── Config ──────────────────────────────────────────────────────────────────
MODEL = os.environ.get("SW_MODEL", "gpt-4o-mini")
BASE_URL = os.environ.get("SW_BASE_URL", None)  # custom endpoint if needed
API_KEY = os.environ.get("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """You are Shell Whisperer, a friendly shell teacher embedded in the terminal.

When the user describes what they want to do, you:
1. Generate the exact shell command(s) to accomplish it
2. Explain what each part does, like a patient tutor
3. Point out any flags or tricks worth learning
4. Warn about potential risks if relevant

Response format — always return valid JSON:
{
  "command": "<the shell command>",
  "explanation": "<step-by-step explanation of the command>",
  "breakdown": [
    {"part": "<part of command>", "meaning": "<what it does>"},
    ...
  ],
  "tip": "<a useful tip or related command worth knowing>",
  "risk": "<any warning, or null if safe>"
}

Keep explanations friendly and educational. Use analogies when helpful.
Assume Linux/macOS bash environment."""

COLORS = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "cyan":   "\033[96m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "gray":   "\033[90m",
    "blue":   "\033[94m",
    "pink":   "\033[95m",
}

def c(color, text):
    return f"{COLORS.get(color,'')}{text}{COLORS['reset']}"

def print_banner():
    print(c("pink", """
  🐚 Shell Whisperer
  ────────────────────────────────────────
  Talk to me in plain language.
  I'll show you the command AND teach you how it works.
  Type 'quit' to exit, 'run' to execute last command.
  ────────────────────────────────────────
"""))

def ask_ai(client, user_input: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(response.choices[0].message.content)

def display_result(result: dict):
    print()
    # The command
    print(c("bold", "  📋 Command:"))
    print(c("cyan", f"     {result['command']}"))
    print()

    # Breakdown
    if result.get("breakdown"):
        print(c("bold", "  🔍 How it works:"))
        for item in result["breakdown"]:
            print(f"     {c('yellow', item['part'])}")
            print(f"       └─ {item['meaning']}")
        print()

    # Explanation
    print(c("bold", "  📖 Explanation:"))
    for line in result["explanation"].split(". "):
        line = line.strip()
        if line:
            print(f"     {line}{'.' if not line.endswith('.') else ''}")
    print()

    # Tip
    if result.get("tip"):
        print(c("green", f"  💡 Tip: {result['tip']}"))
        print()

    # Risk warning
    if result.get("risk"):
        print(c("red", f"  ⚠️  Warning: {result['risk']}"))
        print()

def execute_command(command: str):
    print(c("gray", f"\n  Running: {command}\n  {'─'*40}"))
    try:
        result = subprocess.run(
            command, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(c("red", result.stderr))
        if result.returncode != 0:
            print(c("red", f"\n  Exit code: {result.returncode}"))
        else:
            print(c("green", "\n  ✓ Done!"))
    except Exception as e:
        print(c("red", f"  Error: {e}"))

def check_api_key():
    if not API_KEY:
        print(c("red", """
  ✗ No API key found!
  Set your OpenAI API key:
    export OPENAI_API_KEY="sk-..."
  Or use a custom endpoint:
    export SW_BASE_URL="http://localhost:11434/v1"
    export OPENAI_API_KEY="ollama"
    export SW_MODEL="llama3"
"""))
        sys.exit(1)

def main():
    check_api_key()

    kwargs = {"api_key": API_KEY}
    if BASE_URL:
        kwargs["base_url"] = BASE_URL

    client = OpenAI(**kwargs)

    print_banner()

    last_command = None

    while True:
        try:
            user_input = input(c("pink", "  🐦 What do you want to do? ") + c("bold", "> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print(c("gray", "\n\n  Goodbye! Keep learning! 🌸\n"))
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print(c("gray", "\n  Goodbye! Keep learning! 🌸\n"))
            break

        if user_input.lower() == "run":
            if last_command:
                confirm = input(c("yellow", f"  Run '{last_command}'? [y/N] ")).strip().lower()
                if confirm == "y":
                    execute_command(last_command)
            else:
                print(c("gray", "  No command to run yet."))
            continue

        print(c("gray", "  Thinking..."))

        try:
            result = ask_ai(client, user_input)
            display_result(result)
            last_command = result.get("command")

            if last_command:
                print(c("gray", "  (type 'run' to execute this command)"))
            print()

        except json.JSONDecodeError:
            print(c("red", "  ✗ Couldn't parse AI response. Try again."))
        except Exception as e:
            print(c("red", f"  ✗ Error: {e}"))

if __name__ == "__main__":
    main()
