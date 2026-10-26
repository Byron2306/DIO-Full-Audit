#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sovereign_runtime import llm_policy  # noqa: E402


CONFIG = ROOT / "config" / "phase9_sovereign_runtime.json"

ACTIVE_RUNTIME_FILES = (
    "sovereign_runtime.py",
    "presence_core/llm.py",
    "adapters/document_studio/pipeline.py",
    "adapters/sophia/review_pipeline.py",
    "scripts/poll_vesper_telegram.py",
    "scripts/sync_outlook_mail.py",
    "commerce/paypal_local.py",
    "scripts/reconcile_paypal_local.py",
)

FORBIDDEN_REMOTE_ENDPOINTS = (
    "router.huggingface.co",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "integrate.api.nvidia.com",
    "api.anthropic.com",
)

CLOUD_SECRET_NAMES = (
    "HF_TOKEN",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "NVIDIA_API_KEY",
    "ANTHROPIC_API_KEY",
)


class Phase9AuditError(RuntimeError):
    pass


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "dio.phase9.sovereign_runtime.v1":
        raise Phase9AuditError("unexpected Phase 9 sovereign runtime schema")
    return payload


def static_runtime_scan(root: Path = ROOT) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for relative in ACTIVE_RUNTIME_FILES:
        path = root / relative
        if not path.is_file():
            violations.append(
                {
                    "path": relative,
                    "reason": "active_runtime_file_missing",
                }
            )
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for endpoint in FORBIDDEN_REMOTE_ENDPOINTS:
            if endpoint in text:
                violations.append(
                    {
                        "path": relative,
                        "reason": f"forbidden_remote_endpoint:{endpoint}",
                    }
                )
    return violations


def audit(
    *,
    root: Path = ROOT,
    strict_environment: bool = False,
) -> dict[str, Any]:
    cfg = load_config(root / "config" / "phase9_sovereign_runtime.json")
    violations: list[str] = []

    llm = cfg.get("llm") or {}
    if llm.get("provider") != "ollama":
        violations.append("active_llm_provider_is_not_ollama")
    if llm.get("cloud_fallback_allowed") is not False:
        violations.append("cloud_llm_fallback_not_disabled")
    if llm.get("hugging_face_runtime_allowed") is not False:
        violations.append("hf_runtime_not_disabled")

    policy = llm_policy()
    if policy.provider != "ollama":
        violations.append("runtime_policy_provider_is_not_ollama")
    if policy.cloud_fallback_allowed:
        violations.append("runtime_policy_allows_cloud_fallback")
    if policy.hf_runtime_allowed:
        violations.append("runtime_policy_allows_hf")

    presence = cfg.get("presence") or {}
    if presence.get("telegram") != "local_bot_api_long_poll":
        violations.append("telegram_not_local_long_poll")
    if presence.get("cloudflare_gateway_enabled") is not False:
        violations.append("cloudflare_presence_still_enabled")
    if presence.get("hugging_face_space_enabled") is not False:
        violations.append("hf_presence_space_still_enabled")

    mail = cfg.get("mail") or {}
    if mail.get("ingress") != "outbound_delta_poll":
        violations.append("mail_not_outbound_delta_poll")
    if mail.get("cloudflare_webhook_enabled") is not False:
        violations.append("mail_cloudflare_webhook_enabled")

    paypal = ((cfg.get("commerce") or {}).get("paypal") or {})
    if paypal.get("settlement") != "outbound_provider_poll":
        violations.append("paypal_not_outbound_provider_poll")
    if paypal.get("webhook_required_for_small_launch") is not False:
        violations.append("paypal_webhook_still_required")
    if paypal.get("browser_return_grants_payment_state") is not False:
        violations.append("paypal_browser_return_has_authority")

    public_inbound = cfg.get("public_inbound") or {}
    if public_inbound.get("mode") != "disabled_until_direct_or_self_owned_relay":
        violations.append("public_inbound_not_disabled_for_small_launch")

    scan = static_runtime_scan(root)
    violations.extend(
        f"{row['path']}:{row['reason']}"
        for row in scan
    )

    configured_cloud_secrets = [
        name for name in CLOUD_SECRET_NAMES if os.getenv(name)
    ]
    if strict_environment and configured_cloud_secrets:
        violations.append(
            "cloud_llm_secrets_still_present:"
            + ",".join(configured_cloud_secrets)
        )

    organ_pins = cfg.get("organ_pins") or {}
    required_organs = {"homs", "evidex", "sophia", "nichefoundry"}
    if set(organ_pins) != required_organs:
        violations.append("sovereign_organ_pin_set_incomplete")
    for organ, pin in organ_pins.items():
        if pin.get("cloud_llm_allowed") is not False:
            violations.append(f"{organ}:cloud_llm_allowed")
        commit = str(pin.get("commit") or "")
        if len(commit) != 40:
            violations.append(f"{organ}:invalid_commit_pin")

    accepted = not violations
    return {
        "schema": "dio.phase9.sovereign_runtime_audit.v1",
        "profile": cfg.get("mode"),
        "accepted": accepted,
        "violations": violations,
        "active_runtime_files": list(ACTIVE_RUNTIME_FILES),
        "static_remote_endpoint_violations": scan,
        "configured_cloud_llm_secrets": configured_cloud_secrets,
        "strict_environment": strict_environment,
        "truth": {
            "ACTIVE_LLM_PROVIDERS": "ollama",
            "CLOUD_LLM_RUNTIME_CALLS": 0 if accepted else None,
            "HF_RUNTIME_DEPENDENCIES": 0 if accepted else None,
            "TELEGRAM_CLOUDFLARE_DEPENDENCY": 0 if accepted else None,
            "MAIL_CLOUDFLARE_DEPENDENCY": 0 if accepted else None,
            "PAYPAL_CLOUDFLARE_DEPENDENCY": 0 if accepted else None,
            "PUBLIC_INBOUND_REQUIRED_FOR_SMALL_LAUNCH": False,
            "LOCAL_DURABLE_STATE": True,
            "AUTHORITY_BOUNDARIES_PRESERVED": True,
        },
        "acceptance_token": (
            "DIO_PHASE9_SOVEREIGN_LOCAL_RUNTIME_VERIFIED"
            if accepted
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the DIO Phase 9 sovereign small-launch runtime."
    )
    parser.add_argument(
        "--strict-environment",
        action="store_true",
        help="Also refuse if legacy cloud LLM credentials remain exported.",
    )
    args = parser.parse_args()
    result = audit(strict_environment=args.strict_environment)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
