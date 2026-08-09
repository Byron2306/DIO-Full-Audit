#!/usr/bin/env python3
"""Capture a denial-proof receipt from the live ARDA enforcement path."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.arda_phase4_verifier_service import _Ed25519VerdictSigner  # noqa: E402
from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


DEFAULT_VERDICT = Path("/var/lib/arda/verifier/latest-verdict.json")
DEFAULT_OUTPUT = Path("/var/lib/arda/receipts/latest-denial-proof.json")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sign_receipt(payload: dict[str, Any], *, private_key: str, public_key: str | None, key_id: str) -> dict[str, Any]:
    signer = _Ed25519VerdictSigner(private_key, public_key, key_id=key_id)
    signed = signer.sign(payload)
    return {
        **payload,
        "signature_algorithm": signed["algorithm"],
        "signature": signed["signature"],
        "verification_material": signed["verification_material"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a signed ARDA denial-proof receipt")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--verdict", default=str(DEFAULT_VERDICT))
    parser.add_argument("--test-executable")
    parser.add_argument("--verifier-private-key", default=os.environ.get("ARDA_VERIFIER_PRIVATE_KEY"))
    parser.add_argument("--verifier-public-key", default=os.environ.get("ARDA_VERIFIER_PUBLIC_KEY"))
    parser.add_argument("--verifier-key-id", default=os.environ.get("ARDA_VERIFIER_KEY_ID", "arda-phase4-verifier"))
    args = parser.parse_args()

    service = OsEnforcementService()
    try:
        verdict = _read_json(Path(args.verdict).expanduser().resolve()) if args.verdict else None
        native = service.run_native_denial_self_test()
        status = service.get_status()
        last_deny = status.get("last_deny_event")
        latest_signed_verdict = verdict.get("signed_verdict") if isinstance(verdict, dict) else None
        payload = {
            "schema_version": "arda.phase4.denial_receipt.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kernel": status.get("kernel_release") or os.uname().release,
            "status_summary": {
                "arm_mode": status.get("arm_mode"),
                "enforcement_mode": status.get("enforcement_mode"),
                "is_authoritative": status.get("is_authoritative"),
                "is_simulation": status.get("is_simulation"),
                "attach_verified": status.get("attach_verified"),
                "deny_count": status.get("deny_count"),
            },
            "native_denial_test": native,
            "last_deny_event": last_deny,
            "verifier_verdict": {
                "path": str(Path(args.verdict).expanduser().resolve()) if args.verdict else None,
                "verdict_id": (latest_signed_verdict or {}).get("verdict_id"),
                "ok": (latest_signed_verdict or {}).get("ok"),
                "production_ready": (latest_signed_verdict or {}).get("production_ready"),
                "issued_at": (latest_signed_verdict or {}).get("issued_at"),
            },
        }
        payload["ok"] = bool(native.get("ok")) and bool(last_deny)
        if not payload["ok"]:
            payload["failure"] = native.get("details", {}).get("failure") or "last_deny_event_missing"

        final_payload = payload
        if args.verifier_private_key:
            final_payload = _sign_receipt(
                payload,
                private_key=str(args.verifier_private_key),
                public_key=str(args.verifier_public_key) if args.verifier_public_key else None,
                key_id=str(args.verifier_key_id),
            )

        output_path = Path(args.output).expanduser().resolve()
        _write_json(output_path, final_payload)
        print(json.dumps({"ok": payload["ok"], "output": str(output_path)}, indent=2))
        return 0 if payload["ok"] else 1
    finally:
        service.shutdown()
