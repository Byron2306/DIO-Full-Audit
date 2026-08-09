#!/usr/bin/env python3
"""Optional live Presence server probe for Writing Desk source support.

This is intentionally separate from deterministic Phase 3 CI. It requires the
Presence server to be running and the covenant/session path to permit /api/speak.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def _json_get(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _json_post(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def run_probe(base_url: str, timeout: float) -> dict:
    started = time.time()
    rows = []
    summary = {
        "suite": "sophia_writing_desk_live_probe",
        "base_url": base_url,
        "server_reachable": False,
        "session_token_present": False,
        "speak_released": False,
        "writing_desk_present": False,
        "source_support_present": False,
        "retrieval_or_pool_present": False,
        "passed": False,
        "elapsed_ms": 0,
    }
    try:
        health = _json_get(f"{base_url.rstrip('/')}/api/health", timeout)
        token = health.get("session_token") or ""
        summary["server_reachable"] = health.get("status") == "running"
        summary["session_token_present"] = bool(token)
        rows.append({"step": "health", "passed": summary["server_reachable"], "health": health})
    except Exception as exc:
        summary["elapsed_ms"] = round((time.time() - started) * 1000, 3)
        return {"summary": summary, "rows": [{"step": "health", "passed": False, "error": f"{type(exc).__name__}: {exc}"}]}

    directive = (
        "Writing Desk task: map_sources. Active draft lines 1-1. "
        "Evaluate only the selected/current passage.\n\n"
        "User question/task: Map the current source pool to this exact selected claim using labels: "
        "supports, partially supports, background only, does not support, contradicts, insufficient text.\n\n"
        "Selected passage:\n\"\"\"Academic integrity policies emphasize disclosure, detection, and assessment redesign.\"\"\"\n\n"
        "Integrity/provenance rules: Answer concretely from the active draft and available sources. "
        "Do not invent citations."
    )
    payload = {
        "text": directive,
        "session_token": token,
        "document_evidence_task": "live_writing_desk_probe",
        "document_uploads": [{
            "source_name": "Live Probe Draft",
            "source_path": "live-probe.md",
            "mime_type": "text/markdown",
            "modality": "live_editing_text",
            "parser": "live_probe",
            "extracted_text": "Academic integrity policies emphasize disclosure, detection, and assessment redesign.",
            "spans": [{"span_id": "S1", "quote": "Academic integrity policies emphasize disclosure, detection, and assessment redesign."}],
        }],
        "client_context": {
            "ui_surface": "writing_desk",
            "writing_action": "map_sources",
            "response_mode": "detailed",
            "selected_lines": [1, 1],
        },
    }
    try:
        result = _json_post(f"{base_url.rstrip('/')}/api/speak", payload, timeout)
        wd = result.get("writing_desk") or {}
        source_support = wd.get("source_support") or {}
        summary["speak_released"] = bool(result.get("response"))
        summary["writing_desk_present"] = bool(wd)
        summary["source_support_present"] = bool(source_support)
        summary["retrieval_or_pool_present"] = bool(
            result.get("session_source_pool_size", 0)
            or wd.get("source_pool_count", 0)
            or (source_support.get("sources_considered", 0) > 0)
        )
        rows.append({"step": "speak", "passed": summary["writing_desk_present"], "result": result})
    except Exception as exc:
        rows.append({"step": "speak", "passed": False, "error": f"{type(exc).__name__}: {exc}"})

    summary["passed"] = bool(
        summary["server_reachable"]
        and summary["session_token_present"]
        and summary["speak_released"]
        and summary["writing_desk_present"]
    )
    summary["elapsed_ms"] = round((time.time() - started) * 1000, 3)
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:7070")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--out", default="evidence/sophia_writing_desk_live_probe_latest.json")
    args = parser.parse_args()
    artifact = run_probe(args.base_url, args.timeout)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
