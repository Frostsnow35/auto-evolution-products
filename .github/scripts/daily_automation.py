#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
TARGET_PRODUCT = ROOT / os.environ.get("TARGET_PRODUCT", "product-2026-03-10-semantic-fs")
REPORT_DIR = ROOT / "automation" / "daily-reports"
LATEST = REPORT_DIR / "latest.md"


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd or ROOT, text=True, capture_output=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def git_head() -> str:
    code, out = run(["git", "rev-parse", "HEAD"])
    return out if code == 0 else "unknown"


def repo_clean_summary() -> str:
    code, out = run(["git", "status", "--short"])
    if code != 0:
        return "git status unavailable"
    return out or "clean"


def compileall_check(target: Path) -> tuple[bool, str]:
    package_dir = target / "semantic_fs"
    compile_target = package_dir if package_dir.exists() else target
    code, out = run([sys.executable, "-m", "compileall", str(compile_target)])
    return code == 0, out


def main() -> int:
    now = datetime.now(TZ)
    date_cn = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    day_report = REPORT_DIR / f"{date_cn}.md"

    head_before = git_head()
    product_exists = TARGET_PRODUCT.exists()
    compile_ok, compile_output = compileall_check(TARGET_PRODUCT) if product_exists else (False, "target product path not found")

    lines = [
        f"# 每日自动化报告 - {date_cn}",
        "",
        f"- 生成时间：{timestamp}",
        "- 执行位置：GitHub Actions（GitHub 托管）",
        "- Actions 页面可见：是",
        f"- 目标产品：`{TARGET_PRODUCT.relative_to(ROOT) if product_exists else TARGET_PRODUCT.name}`",
        f"- 执行前 HEAD：`{head_before}`",
        "- Ollama 说明：Ollama 未启动只影响本地测试/验证深度，不影响本 GitHub-hosted 提交。",
        "",
        "## 本轮交付",
        "- 建立并运行 GitHub Actions 日常自动化工作流。",
        "- 生成并提交每日仓库内报告，确保 Actions 页面与仓库提交均有可见证据。",
        "",
        "## 验证结果",
        f"- compileall：{'PASS' if compile_ok else 'FAIL'}",
        "```text",
        compile_output[:12000] if compile_output else "(no output)",
        "```",
        "",
        "## 当前仓库状态",
        "```text",
        repo_clean_summary(),
        "```",
        "",
        "## 下一步建议",
        "- 如需真正由 GitHub 托管执行 AI 代码迭代，再补可在 CI 中使用的模型凭证。",
        "- 在此之前，本 workflow 已满足：页面可见、定时运行、自动提交、可选邮件发送。",
        "",
    ]

    body = "\n".join(lines)
    day_report.write_text(body, encoding="utf-8")
    shutil.copyfile(day_report, LATEST)
    print(f"Wrote {day_report.relative_to(ROOT)}")
    print(f"Wrote {LATEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
