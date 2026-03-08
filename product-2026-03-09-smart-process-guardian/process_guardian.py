#!/usr/bin/env python3
"""
Smart Process Guardian
======================
An AI-powered Linux process monitor that watches running processes,
detects anomalies (high CPU, memory leaks, zombie processes, runaway threads),
and generates human-readable diagnostic summaries + suggested actions via LLM.

Usage:
    python process_guardian.py                  # Interactive scan
    python process_guardian.py --watch 30       # Watch mode, poll every 30s
    python process_guardian.py --pid 1234       # Inspect specific PID
    python process_guardian.py --top 10         # Analyze top 10 CPU hogs
    python process_guardian.py --no-ai          # Report only, no LLM analysis
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
import psutil
from datetime import datetime

# Optional: OpenAI-compatible LLM backend
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class ProcessSnapshot:
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    num_threads: int
    num_fds: int
    create_time: float
    cmdline: str
    username: str
    anomalies: list = field(default_factory=list)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.create_time


@dataclass
class SystemSnapshot:
    timestamp: str
    cpu_percent: float
    memory_percent: float
    swap_percent: float
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    total_processes: int
    zombie_count: int
    processes: list = field(default_factory=list)


# ─── Anomaly Detection ────────────────────────────────────────────────────────

ANOMALY_THRESHOLDS = {
    "high_cpu": 80.0,          # % CPU usage
    "high_memory_mb": 2048,    # 2 GB
    "high_memory_pct": 15.0,   # % of total RAM
    "high_threads": 200,
    "high_fds": 1000,
    "zombie": True,
}


def detect_anomalies(proc: psutil.Process) -> list[str]:
    anomalies = []
    try:
        cpu = proc.cpu_percent(interval=0.1)
        mem_info = proc.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        mem_pct = proc.memory_percent()
        status = proc.status()
        threads = proc.num_threads()

        if status == psutil.STATUS_ZOMBIE:
            anomalies.append("ZOMBIE: process is a zombie (parent not reaping)")
        if cpu > ANOMALY_THRESHOLDS["high_cpu"]:
            anomalies.append(f"HIGH_CPU: {cpu:.1f}% CPU usage")
        if mem_mb > ANOMALY_THRESHOLDS["high_memory_mb"]:
            anomalies.append(f"HIGH_MEM: {mem_mb:.0f} MB RSS")
        if mem_pct > ANOMALY_THRESHOLDS["high_memory_pct"]:
            anomalies.append(f"HIGH_MEM_PCT: {mem_pct:.1f}% of total RAM")
        if threads > ANOMALY_THRESHOLDS["high_threads"]:
            anomalies.append(f"HIGH_THREADS: {threads} threads")
        try:
            fds = proc.num_fds()
            if fds > ANOMALY_THRESHOLDS["high_fds"]:
                anomalies.append(f"HIGH_FDS: {fds} open file descriptors")
        except (psutil.AccessDenied, AttributeError):
            pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return anomalies


def snapshot_process(proc: psutil.Process) -> Optional[ProcessSnapshot]:
    try:
        with proc.oneshot():
            cmdline = " ".join(proc.cmdline()) or proc.name()
            mem = proc.memory_info()
            return ProcessSnapshot(
                pid=proc.pid,
                name=proc.name(),
                status=proc.status(),
                cpu_percent=proc.cpu_percent(interval=0.0),
                memory_mb=mem.rss / 1024 / 1024,
                memory_percent=proc.memory_percent(),
                num_threads=proc.num_threads(),
                num_fds=proc.num_fds() if sys.platform != "win32" else 0,
                create_time=proc.create_time(),
                cmdline=cmdline[:200],
                username=proc.username(),
                anomalies=detect_anomalies(proc),
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def collect_system_snapshot(top_n: int = 20) -> SystemSnapshot:
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    
    all_procs = []
    zombie_count = 0
    
    # First pass: quick scan
    for proc in psutil.process_iter(["pid", "name", "status", "cpu_percent"]):
        try:
            if proc.info["status"] == psutil.STATUS_ZOMBIE:
                zombie_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Short sleep so cpu_percent is meaningful
    time.sleep(0.5)

    # Second pass: full snapshot
    for proc in psutil.process_iter():
        snap = snapshot_process(proc)
        if snap:
            all_procs.append(snap)

    # Sort by CPU then memory
    all_procs.sort(key=lambda p: (p.cpu_percent, p.memory_mb), reverse=True)

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return SystemSnapshot(
        timestamp=datetime.now().isoformat(),
        cpu_percent=psutil.cpu_percent(interval=0.2),
        memory_percent=mem.percent,
        swap_percent=swap.percent,
        load_avg_1m=load[0],
        load_avg_5m=load[1],
        load_avg_15m=load[2],
        total_processes=len(all_procs),
        zombie_count=zombie_count,
        processes=all_procs[:top_n],
    )


# ─── Report Formatting ────────────────────────────────────────────────────────

def format_report(snap: SystemSnapshot) -> str:
    lines = [
        "╔══════════════════════════════════════════════════╗",
        "║        Smart Process Guardian — Scan Report      ║",
        "╚══════════════════════════════════════════════════╝",
        f"  Time       : {snap.timestamp}",
        f"  CPU Usage  : {snap.cpu_percent:.1f}%",
        f"  Memory     : {snap.memory_percent:.1f}%   Swap: {snap.swap_percent:.1f}%",
        f"  Load Avg   : {snap.load_avg_1m:.2f} / {snap.load_avg_5m:.2f} / {snap.load_avg_15m:.2f}",
        f"  Processes  : {snap.total_processes}   Zombies: {snap.zombie_count}",
        "",
    ]

    # Anomalous processes
    anomalous = [p for p in snap.processes if p.anomalies]
    if anomalous:
        lines.append("⚠️  ANOMALOUS PROCESSES:")
        lines.append("─" * 50)
        for p in anomalous:
            lines.append(f"  PID {p.pid:6d}  {p.name[:20]:<20}  {p.status}")
            lines.append(f"    CMD: {p.cmdline[:60]}")
            lines.append(f"    CPU: {p.cpu_percent:.1f}%  MEM: {p.memory_mb:.0f}MB  Threads: {p.num_threads}")
            for a in p.anomalies:
                lines.append(f"    ▶ {a}")
            lines.append("")
    else:
        lines.append("✅  No anomalies detected.")
        lines.append("")

    # Top processes
    lines.append("📊  TOP PROCESSES (by CPU + Memory):")
    lines.append("─" * 50)
    lines.append(f"  {'PID':>7}  {'NAME':<20}  {'CPU%':>6}  {'MEM MB':>8}  {'THREADS':>7}")
    lines.append("  " + "-" * 56)
    for p in snap.processes[:10]:
        flag = " ⚠️" if p.anomalies else ""
        lines.append(
            f"  {p.pid:>7}  {p.name[:20]:<20}  {p.cpu_percent:>6.1f}  {p.memory_mb:>8.0f}  {p.num_threads:>7}{flag}"
        )

    return "\n".join(lines)


# ─── AI Analysis ──────────────────────────────────────────────────────────────

def build_ai_prompt(snap: SystemSnapshot) -> str:
    anomalous = [p for p in snap.processes if p.anomalies]
    proc_data = []
    for p in anomalous[:10]:
        proc_data.append({
            "pid": p.pid,
            "name": p.name,
            "status": p.status,
            "cpu_percent": round(p.cpu_percent, 1),
            "memory_mb": round(p.memory_mb, 1),
            "num_threads": p.num_threads,
            "cmdline": p.cmdline[:100],
            "anomalies": p.anomalies,
            "age_seconds": round(p.age_seconds),
        })

    summary = {
        "system": {
            "cpu": snap.cpu_percent,
            "memory": snap.memory_percent,
            "swap": snap.swap_percent,
            "load_1m": snap.load_avg_1m,
            "zombies": snap.zombie_count,
            "total_processes": snap.total_processes,
        },
        "anomalous_processes": proc_data,
    }

    return f"""You are an expert Linux system administrator and performance engineer.
Analyze the following process snapshot and provide:
1. A brief health assessment (2-3 sentences)
2. For each anomalous process: likely cause + recommended action
3. Any system-wide concerns
4. Specific shell commands to investigate or resolve issues (if applicable)

Be concise and actionable. Use plain text (no markdown headers).

SNAPSHOT:
{json.dumps(summary, indent=2)}
"""


def get_ai_analysis(snap: SystemSnapshot, model: str = "gpt-4o-mini") -> str:
    if not HAS_OPENAI:
        return "(openai package not installed — run: pip install openai)"

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GUARDIAN_API_KEY")
    api_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        return "(OPENAI_API_KEY not set — set it to enable AI analysis)"

    try:
        client = OpenAI(api_key=api_key, base_url=api_base)
        prompt = build_ai_prompt(snap)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(AI analysis failed: {e})"


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_once(args):
    print("🔍 Scanning processes...", flush=True)
    snap = collect_system_snapshot(top_n=args.top)
    
    report = format_report(snap)
    print(report)

    if not args.no_ai:
        anomalous = [p for p in snap.processes if p.anomalies]
        if anomalous or snap.cpu_percent > 80 or snap.memory_percent > 85:
            print("\n🤖 AI ANALYSIS:")
            print("─" * 50)
            analysis = get_ai_analysis(snap, model=args.model)
            print(analysis)
        else:
            print("\n🤖 AI: System looks healthy — no deep analysis needed.")
    
    if args.json:
        output = {
            "timestamp": snap.timestamp,
            "system": asdict(snap),
        }
        # Convert process dataclasses
        output["system"]["processes"] = [asdict(p) for p in snap.processes]
        with open("guardian_report.json", "w") as f:
            json.dump(output, f, indent=2)
        print("\n📄 JSON report saved to guardian_report.json")


def main():
    parser = argparse.ArgumentParser(
        description="Smart Process Guardian — AI-powered Linux process monitor"
    )
    parser.add_argument("--watch", type=int, metavar="SECONDS",
                        help="Watch mode: re-scan every N seconds")
    parser.add_argument("--pid", type=int, help="Inspect a specific PID")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of top processes to analyze (default: 20)")
    parser.add_argument("--no-ai", action="store_true",
                        help="Disable AI analysis (report only)")
    parser.add_argument("--model", default="gpt-4o-mini",
                        help="LLM model to use (default: gpt-4o-mini)")
    parser.add_argument("--json", action="store_true",
                        help="Save JSON report to guardian_report.json")
    parser.add_argument("--threshold-cpu", type=float, default=80.0,
                        help="CPU anomaly threshold %% (default: 80)")
    parser.add_argument("--threshold-mem", type=float, default=2048,
                        help="Memory anomaly threshold MB (default: 2048)")
    args = parser.parse_args()

    # Apply custom thresholds
    ANOMALY_THRESHOLDS["high_cpu"] = args.threshold_cpu
    ANOMALY_THRESHOLDS["high_memory_mb"] = args.threshold_mem

    if args.pid:
        try:
            proc = psutil.Process(args.pid)
            snap = snapshot_process(proc)
            if snap:
                print(f"PID {snap.pid} — {snap.name} ({snap.status})")
                print(f"  CMD      : {snap.cmdline}")
                print(f"  User     : {snap.username}")
                print(f"  CPU      : {snap.cpu_percent:.1f}%")
                print(f"  Memory   : {snap.memory_mb:.0f} MB ({snap.memory_percent:.1f}%)")
                print(f"  Threads  : {snap.num_threads}")
                print(f"  FDs      : {snap.num_fds}")
                print(f"  Age      : {snap.age_seconds:.0f}s")
                if snap.anomalies:
                    print("  Anomalies:")
                    for a in snap.anomalies:
                        print(f"    ▶ {a}")
                else:
                    print("  ✅ No anomalies")
            else:
                print(f"Could not snapshot PID {args.pid}")
        except psutil.NoSuchProcess:
            print(f"PID {args.pid} does not exist")
        return

    if args.watch:
        print(f"👁  Watch mode — scanning every {args.watch}s. Press Ctrl+C to stop.\n")
        try:
            while True:
                os.system("clear")
                run_once(args)
                print(f"\n⏱  Next scan in {args.watch}s…")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nGuardian stopped.")
    else:
        run_once(args)


if __name__ == "__main__":
    main()
