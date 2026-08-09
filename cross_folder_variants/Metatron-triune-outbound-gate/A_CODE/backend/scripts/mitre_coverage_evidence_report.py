#!/usr/bin/env python3
"""Generate MITRE ATT&CK coverage transparency/evidence report."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


BASE_URL = os.environ.get("MITRE_BASE_URL", "http://127.0.0.1:8001/api").rstrip("/")
SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "change-me-setup-token")
ADMIN_EMAIL = os.environ.get("MITRE_REPORT_ADMIN_EMAIL", "admin@local")
ADMIN_PASSWORD = os.environ.get("MITRE_REPORT_ADMIN_PASSWORD", "ChangeMe123!")
ADMIN_NAME = os.environ.get("MITRE_REPORT_ADMIN_NAME", "MITRE Reporter")
TIMEOUT_SECONDS = float(os.environ.get("MITRE_REPORT_TIMEOUT_SECONDS", "20"))

REPORT_DIR = Path(os.environ.get("MITRE_REPORT_DIR", "test_reports"))
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JSON_REPORT = REPORT_DIR / "mitre_coverage_evidence_report.json"
MD_REPORT = REPORT_DIR / "mitre_coverage_evidence_report.md"


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {"raw": resp.text[:800]}


def _ensure_token(session: requests.Session) -> str:
    # Setup may return 201 or 409 when already initialized.
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
        token = (_safe_json(login) or {}).get("access_token")
        if isinstance(token, str) and token:
            return token

    # fallback user registration
    suffix = str(int(time.time()))
    email = f"mitre-evidence-{suffix}@local"
    password = "ChangeMe123!"
    session.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "name": "MITRE Evidence"},
        timeout=TIMEOUT_SECONDS,
    )
    login = session.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=TIMEOUT_SECONDS,
    )
    if login.status_code != 200:
        raise RuntimeError(f"Authentication failed ({login.status_code}): {login.text[:500]}")
    token = (_safe_json(login) or {}).get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Authentication succeeded but no access_token returned")
    return token


def _coverage_snapshot(session: requests.Session, token: str, profile: str) -> Dict[str, Any]:
    resp = session.get(
        f"{BASE_URL}/mitre/coverage",
        params={"profile": profile},
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT_SECONDS,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Coverage request failed for profile={profile} ({resp.status_code}): {resp.text[:600]}"
        )
    payload = _safe_json(resp)
    techniques = payload.get("techniques") if isinstance(payload.get("techniques"), list) else []
    return {
        "profile": profile,
        "metrics": {
            "coverage_percent_gte2": payload.get("coverage_percent_gte2"),
            "coverage_percent_gte3": payload.get("coverage_percent_gte3"),
            "coverage_percent_gte4": payload.get("coverage_percent_gte4"),
            "covered_score_gte3": payload.get("covered_score_gte3"),
            "covered_score_gte4": payload.get("covered_score_gte4"),
            "enterprise_covered_parent_techniques_gte3": payload.get(
                "enterprise_covered_parent_techniques_gte3"
            ),
            "enterprise_covered_parent_techniques_gte4": payload.get(
                "enterprise_covered_parent_techniques_gte4"
            ),
            "priority_gap_covered_gte3": payload.get("priority_gap_covered_gte3"),
            "priority_gap_covered_gte4": payload.get("priority_gap_covered_gte4"),
        },
        "scoring_profile": payload.get("scoring_profile") or {},
        "scoring_pass_trace": payload.get("scoring_pass_trace") or [],
        "techniques": techniques,
    }


def _score_index(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for row in snapshot.get("techniques") or []:
        technique = str(row.get("technique") or "").strip().upper()
        if not technique:
            continue
        index[technique] = row
    return index


def _build_delta(before: Dict[str, Any], after: Dict[str, Any], *, top_n: int = 30) -> Dict[str, Any]:
    before_idx = _score_index(before)
    after_idx = _score_index(after)
    all_techniques = sorted(set(before_idx.keys()) | set(after_idx.keys()))

    changed: List[Dict[str, Any]] = []
    promoted_to_gte3 = 0
    promoted_to_gte4 = 0
    regressed = 0

    for technique in all_techniques:
        prev = before_idx.get(technique, {})
        curr = after_idx.get(technique, {})
        prev_score = int(prev.get("score", 0))
        curr_score = int(curr.get("score", 0))
        if prev_score == curr_score:
            continue

        if prev_score < 3 <= curr_score:
            promoted_to_gte3 += 1
        if prev_score < 4 <= curr_score:
            promoted_to_gte4 += 1
        if curr_score < prev_score:
            regressed += 1

        changed.append(
            {
                "technique": technique,
                "from_score": prev_score,
                "to_score": curr_score,
                "delta": curr_score - prev_score,
                "sources_after": curr.get("sources") or [],
                "operational_evidence_after": bool(curr.get("operational_evidence")),
                "implemented_evidence_count_after": int(curr.get("implemented_evidence_count") or 0),
            }
        )

    changed.sort(key=lambda row: (row["delta"], row["to_score"], row["implemented_evidence_count_after"]), reverse=True)
    return {
        "changed_techniques": len(changed),
        "promoted_to_gte3": promoted_to_gte3,
        "promoted_to_gte4": promoted_to_gte4,
        "regressed_techniques": regressed,
        "top_changes": changed[:top_n],
    }


def _assertions(strict: Dict[str, Any], balanced: Dict[str, Any], hardened: Dict[str, Any]) -> Dict[str, Any]:
    strict_m = strict.get("metrics") or {}
    balanced_m = balanced.get("metrics") or {}
    hardened_m = hardened.get("metrics") or {}
    hardened_ready = bool(
        ((hardened.get("scoring_profile") or {}).get("hardened_prerequisites") or {}).get("hardened_mode_ready")
    )

    balanced_gte3 = float(balanced_m.get("coverage_percent_gte3") or 0.0)
    strict_gte3 = float(strict_m.get("coverage_percent_gte3") or 0.0)
    balanced_gte4 = float(balanced_m.get("coverage_percent_gte4") or 0.0)
    hardened_gte4 = float(hardened_m.get("coverage_percent_gte4") or 0.0)

    return {
        "balanced_gte3_not_lower_than_strict": balanced_gte3 >= strict_gte3,
        "hardened_prerequisites_ready": hardened_ready,
        "hardened_gte4_not_lower_than_balanced": hardened_gte4 >= balanced_gte4,
        "summary": {
            "strict_gte3": strict_gte3,
            "balanced_gte3": balanced_gte3,
            "balanced_gte4": balanced_gte4,
            "hardened_gte4": hardened_gte4,
        },
    }


def _write_markdown(report: Dict[str, Any]) -> None:
    profiles = report.get("profiles") or {}
    strict = profiles.get("strict") or {}
    balanced = profiles.get("balanced") or {}
    hardened = profiles.get("hardened") or {}
    deltas = report.get("deltas") or {}
    assertions = report.get("assertions") or {}

    def metric_row(label: str, key: str) -> str:
        s = (strict.get("metrics") or {}).get(key)
        b = (balanced.get("metrics") or {}).get(key)
        h = (hardened.get("metrics") or {}).get(key)
        return f"| {label} | {s} | {b} | {h} |"

    lines = [
        "# MITRE Coverage Evidence Report",
        "",
        f"- Generated: {report.get('generated_at')}",
        f"- Base URL: `{report.get('base_url')}`",
        "",
        "## Profile Metrics",
        "",
        "| Metric | strict | balanced | hardened |",
        "|---|---:|---:|---:|",
        metric_row("coverage_percent_gte2", "coverage_percent_gte2"),
        metric_row("coverage_percent_gte3", "coverage_percent_gte3"),
        metric_row("coverage_percent_gte4", "coverage_percent_gte4"),
        metric_row("covered_score_gte3", "covered_score_gte3"),
        metric_row("covered_score_gte4", "covered_score_gte4"),
        metric_row("enterprise_parents_gte3", "enterprise_covered_parent_techniques_gte3"),
        metric_row("enterprise_parents_gte4", "enterprise_covered_parent_techniques_gte4"),
        "",
        "## Hardened Prerequisites",
        "",
        "```json",
        json.dumps(((hardened.get("scoring_profile") or {}).get("hardened_prerequisites") or {}), indent=2),
        "```",
        "",
        "## Scoring Pass Trace (hardened profile request)",
        "",
        "| Pass | Enabled | Changed | Promoted >=3 | Promoted >=4 |",
        "|---|---|---:|---:|---:|",
    ]

    for item in (hardened.get("scoring_pass_trace") or []):
        lines.append(
            f"| `{item.get('pass')}` | {bool(item.get('enabled'))} | {item.get('changed_techniques')} | "
            f"{item.get('promoted_to_gte3')} | {item.get('promoted_to_gte4')} |"
        )

    lines.extend(
        [
            "",
            "## Delta Summary",
            "",
            "```json",
            json.dumps(deltas, indent=2),
            "```",
            "",
            "## Assertions",
            "",
            "```json",
            json.dumps(assertions, indent=2),
            "```",
            "",
            "_Interpretation_: strict disables inferred/promotion passes; balanced enables operational/corroboration passes; "
            "hardened additionally requires strong JWT + Trivy prerequisites.",
            "",
        ]
    )

    MD_REPORT.write_text("\n".join(lines), encoding="utf-8")


def run() -> int:
    session = requests.Session()
    token = _ensure_token(session)

    strict = _coverage_snapshot(session, token, "strict")
    balanced = _coverage_snapshot(session, token, "balanced")
    hardened = _coverage_snapshot(session, token, "hardened")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "profiles": {
            "strict": strict,
            "balanced": balanced,
            "hardened": hardened,
        },
        "deltas": {
            "strict_to_balanced": _build_delta(strict, balanced),
            "balanced_to_hardened": _build_delta(balanced, hardened),
        },
        "assertions": _assertions(strict, balanced, hardened),
    }

    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report)
    print(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "strict_gte3": strict["metrics"].get("coverage_percent_gte3"),
                "balanced_gte3": balanced["metrics"].get("coverage_percent_gte3"),
                "balanced_gte4": balanced["metrics"].get("coverage_percent_gte4"),
                "hardened_gte4": hardened["metrics"].get("coverage_percent_gte4"),
                "report_json": str(JSON_REPORT),
                "report_md": str(MD_REPORT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
