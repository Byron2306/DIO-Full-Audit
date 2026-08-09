#!/usr/bin/env python3
"""Bring up full stack services and run robust E2E validation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set

import requests


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "test_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JSON_REPORT = REPORT_DIR / "full_stack_validation_report.json"
MD_REPORT = REPORT_DIR / "full_stack_validation_report.md"

BASE_URL = os.environ.get("FULL_STACK_BASE_URL", "http://127.0.0.1:8001/api").rstrip("/")
SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "change-me-setup-token")
ADMIN_EMAIL = os.environ.get("FULL_STACK_ADMIN_EMAIL", "admin@local")
ADMIN_PASSWORD = os.environ.get("FULL_STACK_ADMIN_PASSWORD", "ChangeMe123!")
ADMIN_NAME = os.environ.get("FULL_STACK_ADMIN_NAME", "Full Stack Validator")
TIMEOUT_SECONDS = float(os.environ.get("FULL_STACK_HTTP_TIMEOUT_SECONDS", "10"))
READINESS_TIMEOUT_SECONDS = int(os.environ.get("FULL_STACK_READINESS_TIMEOUT_SECONDS", "300"))
SKIP_COMPOSE_UP = os.environ.get("FULL_STACK_SKIP_COMPOSE_UP", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

REQUIRED_SERVICES = [
    "mongodb",
    "redis",
    "backend",
    "frontend",
    "celery-worker",
    "celery-beat",
    "elasticsearch",
    "kibana",
    "trivy",
    "falco",
    "suricata",
    "zeek",
    "volatility",
    "wireguard",
    "nginx",
    "cuckoo-mongo",
    "cuckoo",
    "cuckoo-web",
]


def _run_cmd(cmd: Sequence[str], *, timeout: int = 1200) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
            "elapsed_ms": round(elapsed_ms, 2),
        }
    except FileNotFoundError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "cmd": " ".join(cmd),
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
            "elapsed_ms": round(elapsed_ms, 2),
        }


def _compose_services_declared() -> Set[str]:
    result = _run_cmd(["docker", "compose", "config", "--services"], timeout=180)
    if result["returncode"] != 0:
        return set()
    return {line.strip() for line in str(result["stdout"]).splitlines() if line.strip()}


def _compose_services_running() -> Set[str]:
    result = _run_cmd(["docker", "compose", "ps", "--services", "--status", "running"], timeout=120)
    if result["returncode"] != 0:
        return set()
    return {line.strip() for line in str(result["stdout"]).splitlines() if line.strip()}


def _wait_http(url: str, *, expected: Set[int], timeout_seconds: int) -> Dict[str, Any]:
    started = time.perf_counter()
    deadline = time.time() + timeout_seconds
    attempts = 0
    last_status = None
    last_error = ""
    while time.time() < deadline:
        attempts += 1
        try:
            resp = requests.get(url, timeout=TIMEOUT_SECONDS)
            last_status = resp.status_code
            if resp.status_code in expected:
                return {
                    "ok": True,
                    "status_code": resp.status_code,
                    "attempts": attempts,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
                }
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2.0)
    return {
        "ok": False,
        "status_code": last_status,
        "attempts": attempts,
        "error": last_error,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
    }


def _ensure_token(session: requests.Session) -> str:
    try:
        session.post(
            f"{BASE_URL}/auth/setup",
            headers={"X-Setup-Token": SETUP_TOKEN},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "name": ADMIN_NAME},
            timeout=TIMEOUT_SECONDS,
        )
    except Exception:
        pass

    login = session.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT_SECONDS,
    )
    if login.status_code == 200:
        token = (login.json() or {}).get("access_token")
        if isinstance(token, str) and token:
            return token

    # fallback dedicated user
    suffix = str(int(time.time()))
    email = f"full-stack-{suffix}@local"
    password = "ChangeMe123!"
    session.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "name": "Full Stack"},
        timeout=TIMEOUT_SECONDS,
    )
    login = session.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=TIMEOUT_SECONDS,
    )
    if login.status_code != 200:
        raise RuntimeError(f"Unable to authenticate for API probes: {login.status_code} {login.text[:400]}")
    token = (login.json() or {}).get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Missing access_token for API probes")
    return token


def _api_probe(session: requests.Session, token: str, method: str, path: str, expected: Set[int]) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    started = time.perf_counter()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = session.request(method, url, headers=headers, timeout=TIMEOUT_SECONDS)
        ok = response.status_code in expected
        body: Any
        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text[:200]}
        return {
            "method": method,
            "path": path,
            "expected": sorted(expected),
            "status_code": response.status_code,
            "ok": ok,
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
            "body_preview": body,
        }
    except Exception as exc:
        return {
            "method": method,
            "path": path,
            "expected": sorted(expected),
            "status_code": None,
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 2),
            "error": str(exc),
        }


def _run_suite(cmd: Sequence[str]) -> Dict[str, Any]:
    result = _run_cmd(cmd, timeout=2400)
    return {
        "cmd": result["cmd"],
        "returncode": result["returncode"],
        "elapsed_ms": result["elapsed_ms"],
        "ok": result["returncode"] == 0,
        "stdout_tail": result["stdout"][-2500:],
        "stderr_tail": result["stderr"][-2500:],
    }


def _write_markdown(report: Dict[str, Any]) -> None:
    compose = report.get("compose") or {}
    readiness = report.get("readiness") or {}
    probes = report.get("api_probes") or []
    suites = report.get("suite_runs") or []

    lines = [
        "# Full Stack Validation Report",
        "",
        f"- Generated: {report.get('generated_at')}",
        f"- Overall Passed: **{report.get('overall_passed')}**",
        f"- Base URL: `{report.get('base_url')}`",
        "",
        "## Compose Services",
        "",
        f"- Declared services: **{len(compose.get('declared_services') or [])}**",
        f"- Running services: **{len(compose.get('running_services') or [])}**",
        f"- Missing required services: **{len(compose.get('missing_required_services') or [])}**",
        "",
        "```json",
        json.dumps(compose, indent=2),
        "```",
        "",
        "## Readiness Checks",
        "",
        "```json",
        json.dumps(readiness, indent=2),
        "```",
        "",
        "## API Probes",
        "",
        "| Method | Path | Status | OK |",
        "|---|---|---:|---|",
    ]
    for probe in probes:
        lines.append(
            f"| `{probe.get('method')}` | `{probe.get('path')}` | {probe.get('status_code')} | {probe.get('ok')} |"
        )

    lines.extend(
        [
            "",
            "## Suite Runs",
            "",
            "| Command | Exit | OK | Duration (ms) |",
            "|---|---:|---|---:|",
        ]
    )
    for suite in suites:
        lines.append(
            f"| `{suite.get('cmd')}` | {suite.get('returncode')} | {suite.get('ok')} | {suite.get('elapsed_ms')} |"
        )

    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> int:
    docker_available = shutil.which("docker") is not None
    compose_steps: List[Dict[str, Any]] = []
    if docker_available and not SKIP_COMPOSE_UP:
        compose_steps.append(
            _run_cmd(
                [
                    "docker",
                    "compose",
                    "--profile",
                    "security",
                    "--profile",
                    "sandbox",
                    "--profile",
                    "bootstrap",
                    "up",
                    "-d",
                    "--remove-orphans",
                ],
                timeout=1800,
            )
        )
    elif not docker_available:
        compose_steps.append(
            {
                "cmd": "docker compose ...",
                "returncode": 127,
                "stdout": "",
                "stderr": "docker executable not found on PATH",
                "elapsed_ms": 0.0,
            }
        )

    declared = sorted(_compose_services_declared()) if docker_available else []
    running = sorted(_compose_services_running()) if docker_available else []
    missing_required = sorted(set(REQUIRED_SERVICES) - set(running))

    readiness: Dict[str, Dict[str, Any]] = {
        "backend_health": _wait_http(
            f"{BASE_URL}/health",
            expected={200},
            timeout_seconds=min(READINESS_TIMEOUT_SECONDS, 90) if not docker_available else READINESS_TIMEOUT_SECONDS,
        ),
    }
    if docker_available:
        readiness["frontend_root"] = _wait_http(
            "http://127.0.0.1:3000",
            expected={200},
            timeout_seconds=READINESS_TIMEOUT_SECONDS,
        )
        readiness["kibana_root"] = _wait_http(
            "http://127.0.0.1:5601",
            expected={200, 302},
            timeout_seconds=READINESS_TIMEOUT_SECONDS,
        )
        readiness["elasticsearch_root"] = _wait_http(
            "http://127.0.0.1:9200",
            expected={200, 401},
            timeout_seconds=READINESS_TIMEOUT_SECONDS,
        )
    else:
        for key in ("frontend_root", "kibana_root", "elasticsearch_root"):
            readiness[key] = {
                "ok": None,
                "skipped": True,
                "reason": "docker unavailable in current runtime",
            }

    session = requests.Session()
    token = _ensure_token(session)
    probes = [
        _api_probe(session, token, "GET", "/containers/falco/status", {200}),
        _api_probe(session, token, "GET", "/containers/suricata/stats", {200}),
        _api_probe(session, token, "GET", "/zeek/status", {200}),
        _api_probe(session, token, "GET", "/advanced/sandbox/status", {200}),
        _api_probe(session, token, "GET", "/settings/elasticsearch/status", {200}),
        _api_probe(session, token, "GET", "/kibana/status", {200}),
        _api_probe(session, token, "GET", "/mitre/coverage?profile=balanced", {200}),
        _api_probe(session, token, "GET", "/mitre/coverage?profile=hardened", {200}),
    ]

    # Ensure child suites target the same backend under test.
    os.environ["E2E_BASE_URL"] = BASE_URL
    os.environ["MITRE_BASE_URL"] = BASE_URL

    suite_runs = [
        _run_suite([sys.executable, "backend/scripts/e2e_endpoint_sweep.py"]),
        _run_suite([sys.executable, "backend/scripts/e2e_threat_pipeline_test.py"]),
        _run_suite([sys.executable, "backend/scripts/mitre_coverage_evidence_report.py"]),
    ]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "compose": {
            "docker_available": docker_available,
            "steps": compose_steps,
            "declared_services": declared,
            "running_services": running,
            "required_services": REQUIRED_SERVICES,
            "missing_required_services": missing_required,
        },
        "readiness": readiness,
        "api_probes": probes,
        "suite_runs": suite_runs,
    }

    compose_ok = docker_available and len(missing_required) == 0
    readiness_ok = all(bool(item.get("ok")) or bool(item.get("skipped")) for item in readiness.values())
    probes_ok = all(bool(item.get("ok")) for item in probes)
    suites_ok = all(bool(item.get("ok")) for item in suite_runs)
    report["overall_passed"] = bool(compose_ok and readiness_ok and probes_ok and suites_ok)

    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report)
    print(
        json.dumps(
            {
                "overall_passed": report["overall_passed"],
                "missing_required_services": missing_required,
                "readiness_ok": readiness_ok,
                "api_probes_ok": probes_ok,
                "suite_runs_ok": suites_ok,
                "report_json": str(JSON_REPORT),
                "report_md": str(MD_REPORT),
            },
            indent=2,
        )
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
