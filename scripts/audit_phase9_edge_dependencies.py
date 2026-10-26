#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ACTIVE_EDGE_RUNTIME_FILES = [
    Path("scripts/poll_vesper_telegram.py"),
    Path("scripts/serve_presence_bridge.py"),
    Path("scripts/sync_outlook_mail.py"),
    Path("scripts/create_dio_order.py"),
    Path("scripts/create_paypal_checkout.py"),
    Path("scripts/reconcile_paypal_local.py"),
    Path("scripts/manage_sophia_commercial.py"),
    Path("scripts/manage_vamp_commercial.py"),
    Path("scripts/serve_public_edge_local.py"),
    Path("commerce/paypal_local.py"),
    Path("commerce/public_intake_local.py"),
    Path("sites/assets/dio-public-intake.js"),
]

FORBIDDEN_ACTIVE_MARKERS = {
    "workers.dev": "cloudflare_worker_url",
    "wrangler": "cloudflare_wrangler",
    "from scripts.sync_dio_edge_events": "legacy_edge_client_import",
    "import scripts.sync_dio_edge_events": "legacy_edge_client_import",
    "router.huggingface.co": "hugging_face_router",
    "HF_TOKEN": "hugging_face_token",
    "DIO_PRESENCE_HF_MODEL": "hugging_face_model",
}


def audit() -> dict:
    findings = []
    inspected = []
    for relative in ACTIVE_EDGE_RUNTIME_FILES:
        path = ROOT / relative
        if not path.is_file():
            findings.append(
                {
                    "path": str(relative),
                    "kind": "missing_active_runtime_file",
                    "marker": None,
                }
            )
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        inspected.append(str(relative))
        for marker, kind in FORBIDDEN_ACTIVE_MARKERS.items():
            if marker in text:
                findings.append(
                    {
                        "path": str(relative),
                        "kind": kind,
                        "marker": marker,
                    }
                )

    profile = json.loads(
        (ROOT / "config" / "phase9_sovereign_runtime.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        "telegram_cloudflare": profile["presence"]["cloudflare_gateway_enabled"],
        "mail_cloudflare": profile["mail"]["cloudflare_webhook_enabled"],
        "hf_space": profile["presence"]["hugging_face_space_enabled"],
    }
    for label, value in expected.items():
        if value is not False:
            findings.append(
                {
                    "path": "config/phase9_sovereign_runtime.json",
                    "kind": f"active_external_dependency:{label}",
                    "marker": str(value),
                }
            )

    return {
        "schema": "dio.phase9.edge_dependency_audit.v1",
        "active_runtime_files": inspected,
        "findings": findings,
        "telegram_cloudflare_dependency": 0
        if profile["presence"]["cloudflare_gateway_enabled"] is False
        else 1,
        "mail_cloudflare_dependency": 0
        if profile["mail"]["cloudflare_webhook_enabled"] is False
        else 1,
        "paypal_cloudflare_dependency": 0
        if profile["commerce"]["paypal"]["settlement"]
        == "outbound_provider_poll"
        else 1,
        "hf_runtime_dependency": 0
        if profile["presence"]["hugging_face_space_enabled"] is False
        else 1,
        "legacy_cloudflare_retained_for_rollback": (
            profile["legacy"]["cloudflare_worker"] == "rollback_only"
        ),
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["findings"]:
        return 1
    print("TELEGRAM_CLOUDFLARE_DEPENDENCY=0")
    print("MAIL_CLOUDFLARE_DEPENDENCY=0")
    print("PAYPAL_CLOUDFLARE_DEPENDENCY=0")
    print("HF_RUNTIME_DEPENDENCIES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
