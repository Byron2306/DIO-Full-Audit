#!/usr/bin/env python3
"""Probe Sophia reasoned-lane providers through the real presence API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.request import Request, urlopen

from sophia_matrix_gauntlet import PROVIDER_PRESETS, load_env_file


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evidence" / "provider_probe"


def request_json(url: str, payload: Dict[str, Any] | None = None, timeout: int = 120) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def classify_error(error: str) -> str:
    lowered = (error or "").lower()
    if "missing_api_key" in lowered:
        return "missing_key"
    if "empty_response" in lowered or "provider_empty_or_degraded" in lowered:
        return "empty_or_degraded_response"
    if "401" in lowered or "invalid_api_key" in lowered or "unauthorized" in lowered:
        return "invalid_key"
    if "402" in lowered or "insufficient" in lowered or "credit" in lowered or "balance" in lowered:
        return "quota_or_credit"
    if "403" in lowered or "1010" in lowered or "cloudflare" in lowered or "access denied" in lowered:
        return "network_or_signature_block"
    if "404" in lowered or "model" in lowered and "not found" in lowered:
        return "model_or_endpoint"
    if "429" in lowered or "rate" in lowered:
        return "rate_limited"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    return "unknown_error"


def provider_key_names(provider: str) -> List[str]:
    mapping = {
        "cohere": ["COHERE_API_KEY"],
        "nim": ["NVIDIA_API_KEY", "NIM_API_KEY"],
        "nvidia_nim": ["NVIDIA_API_KEY", "NIM_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "cerebras": ["CEREBRAS_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "novita": ["NOVITA_API_KEY"],
    }
    return mapping.get(provider, [])


def configured(provider: str) -> bool:
    return any(bool(os.environ.get(key)) for key in provider_key_names(provider))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:7070")
    parser.add_argument("--providers", choices=sorted(PROVIDER_PRESETS), default="live_remote")
    parser.add_argument("--env-file", default="")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    providers = PROVIDER_PRESETS[args.providers]
    loaded = load_env_file(args.env_file, [item["provider"] for item in providers])
    try:
        health = request_json(f"{args.base_url}/api/health", timeout=20)
    except Exception as exc:
        print(f"Presence server unavailable: {exc}", file=sys.stderr)
        return 2
    token = health.get("session_token")
    if not token:
        print("Presence server did not return session_token.", file=sys.stderr)
        return 2

    rows: List[Dict[str, Any]] = []
    for provider in providers:
        started = time.perf_counter()
        payload = {
            "session_token": token,
            "text": "Provider unblock probe. Reply with exactly: OK",
            "requested_office": "speculum",
            "reasoned_integrity_lane": True,
            "reasoned_provider": provider["provider"],
            "reasoned_model": provider["model"],
            "reasoned_max_predict": 12,
            "disable_continuity_memory": True,
            "disable_world_events": True,
        }
        result: Dict[str, Any]
        transport_error = ""
        try:
            result = request_json(f"{args.base_url}/api/speak", payload=payload, timeout=args.timeout)
        except Exception as exc:
            result = {}
            transport_error = f"{type(exc).__name__}: {exc}"
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        raw_error = str((result.get("reasoned_provider_error") or result.get("transport_error") or transport_error or ""))
        raw_text = str(result.get("model_response_raw") or result.get("model_response_after_thinking") or "")
        ok = bool(raw_text.strip()) and not raw_error
        repair_steps = result.get("repair_steps") or []
        if not raw_error and not raw_text.strip() and repair_steps:
            raw_error = "provider_empty_or_degraded:" + "; ".join(str(step) for step in repair_steps[:3])
        rows.append({
            "provider": provider["provider"],
            "model": provider["model"],
            "configured": configured(provider["provider"]),
            "ok": ok,
            "failure_class": None if ok else classify_error(raw_error or str(result)[:500]),
            "ms": elapsed,
            "raw_response_hash": None if not raw_text else __import__("hashlib").sha256(raw_text.encode("utf-8")).hexdigest(),
            "error_excerpt": raw_error[:500],
            "source": result.get("source"),
            "release_passed": bool((result.get("mandos_judgment") or {}).get("passed")),
        })
        status = "OK" if ok else "BLOCKED"
        print(f"{status} {provider['provider']}::{provider['model']} {rows[-1]['failure_class'] or ''}", flush=True)

    summary = {
        "total": len(rows),
        "ok": sum(1 for row in rows if row["ok"]),
        "configured": sum(1 for row in rows if row["configured"]),
        "by_failure_class": {},
        "env_keys_loaded": sorted(set(loaded)),
    }
    for row in rows:
        key = row["failure_class"] or "ok"
        summary["by_failure_class"][key] = summary["by_failure_class"].get(key, 0) + 1

    artifact = {
        "schema_version": "sophia.provider_unblock_probe.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "providers_preset": args.providers,
        "summary": summary,
        "rows": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"sophia_provider_unblock_probe_{stamp}.json"
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"artifact": str(out), "summary": summary}, indent=2))
    return 0 if summary["ok"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
