#!/usr/bin/env python3
"""
Integration Runtime Full Smoke
==============================

Performs a non-destructive runtime smoke test for all integrated tools using
the unified `/api/integrations/runtime/run` endpoint with `action=status`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

import requests

BASE_URL = os.environ.get("INTEGRATION_SMOKE_BASE_URL", "http://127.0.0.1:8051/api").rstrip("/")
ADMIN_EMAIL = os.environ.get("INTEGRATION_SMOKE_ADMIN_EMAIL", "admin@local")
ADMIN_PASSWORD = os.environ.get("INTEGRATION_SMOKE_ADMIN_PASSWORD", "ChangeMe123!")
ADMIN_NAME = os.environ.get("INTEGRATION_SMOKE_ADMIN_NAME", "Integration Smoke Admin")

TOOLS = [
    "amass",
    "arkime",
    "bloodhound",
    "spiderfoot",
    "velociraptor",
    "purplesharp",
    "sigma",
    "atomic",
    "trivy",
    "falco",
    "suricata",
    "yara",
    "cuckoo",
    "osquery",
    "zeek",
]


def _ensure_auth() -> str:
    requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "name": ADMIN_NAME},
        timeout=20,
    )
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def run() -> Dict[str, Any]:
    token = _ensure_auth()
    headers = {"Authorization": f"Bearer {token}"}
    results: Dict[str, Any] = {}

    for tool in TOOLS:
        payload = {
            "tool": tool,
            "runtime_target": "server",
            "params": {"action": "status"},
        }
        try:
            resp = requests.post(
                f"{BASE_URL}/integrations/runtime/run",
                json=payload,
                headers=headers,
                timeout=60,
            )
            body = resp.json() if resp.content else {}
            results[tool] = {
                "http_status": resp.status_code,
                "job_status": body.get("status"),
                "job_id": body.get("job_id"),
                "queue_id": body.get("queue_id"),
                "decision_id": body.get("decision_id"),
            }
        except Exception as exc:
            results[tool] = {"error": str(exc)}

    passed = [t for t, row in results.items() if row.get("http_status") == 200 and row.get("job_status") == "completed"]
    failed = [t for t in TOOLS if t not in passed]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((len(passed) / len(TOOLS)) * 100.0, 2) if TOOLS else 0.0,
        "results": results,
    }


def main() -> None:
    report = run()
    out_dir = Path("test_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "integration_runtime_full_smoke.json"
    out_md = out_dir / "integration_runtime_full_smoke.md"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Integration Runtime Full Smoke",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Base URL: `{report['base_url']}`",
        f"- Pass rate: **{report['pass_rate']}%**",
        "",
        "## Summary",
        "",
        f"- Passed: {len(report['passed'])}",
        f"- Failed: {len(report['failed'])}",
        "",
        "## Per-tool Status",
        "",
        "| Tool | HTTP | Job status |",
        "|---|---:|---|",
    ]
    for tool in TOOLS:
        row = report["results"].get(tool, {})
        lines.append(f"| {tool} | {row.get('http_status', 'ERR')} | {row.get('job_status', row.get('error', 'unknown'))} |")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "report_json": str(out_json),
                "report_md": str(out_md),
                "pass_rate": report["pass_rate"],
                "failed": report["failed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
