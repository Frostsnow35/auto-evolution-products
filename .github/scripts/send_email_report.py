#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import format_datetime, make_msgid
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
PROOF_PATH = ROOT / "automation" / "daily-reports" / "last_email_delivery.json"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: send_email_report.py <report-path>", file=sys.stderr)
        return 2

    required = ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM", "REPORT_EMAIL_TO"]
    missing = [key for key in required if not os.environ.get(key, "").strip()]
    if missing:
        print(json.dumps({"status": "skipped", "reason": "missing_smtp_env", "missing": missing}, ensure_ascii=False))
        return 0

    report_path = (ROOT / sys.argv[1]).resolve()
    body = report_path.read_text(encoding="utf-8") if report_path.exists() else "No report file was found."
    now = datetime.now(TZ)
    subject = f"Daily Automation Report - {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    message_id = make_msgid(domain=os.environ["SMTP_HOST"])

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = os.environ["REPORT_EMAIL_TO"]
    msg["Date"] = format_datetime(now)
    msg["Message-ID"] = message_id

    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=30) as server:
        server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        server.send_message(msg)

    PROOF_PATH.parent.mkdir(parents=True, exist_ok=True)
    proof = {
        "status": "sent",
        "sent_at": now.isoformat(),
        "timezone": "Asia/Shanghai",
        "to": os.environ["REPORT_EMAIL_TO"],
        "from": os.environ["SMTP_FROM"],
        "subject": subject,
        "message_id": message_id,
        "smtp_host": os.environ["SMTP_HOST"],
        "smtp_port": port,
        "report_path": str(report_path.relative_to(ROOT)),
        "report_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }
    PROOF_PATH.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
