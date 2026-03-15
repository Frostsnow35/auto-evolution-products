# GitHub Actions Daily Automation

This repository now contains a GitHub-hosted daily automation workflow:

- File: `.github/workflows/daily-automation.yml`
- Schedule: `0 18 * * *` UTC = `02:00` Asia/Shanghai
- Trigger: scheduled + manual `workflow_dispatch`
- Visibility: appears in the GitHub Actions page

What it currently guarantees
- GitHub-hosted execution
- Daily visible run record on the Actions page
- Daily committed report under `automation/daily-reports/`
- Optional SMTP email delivery when secrets are configured

Important note
- Ollama is **not required** for this workflow.
- Ollama not running only affects local validation depth; it does **not** block this GitHub-hosted submission.

Required email secrets (optional)
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `REPORT_EMAIL_TO`

Future upgrade path
- If you want GitHub Actions to perform AI-driven code edits, add a CI-usable model credential.
- Until then, this workflow still satisfies: visible, scheduled, GitHub-hosted, auto-commit, optional auto-email.
