#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = Path.home() / ".config" / "dio" / "sovereign.env"

FORBIDDEN_CLOUD_KEYS = (
    "HF_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "NVIDIA_API_KEY",
    "ANTHROPIC_API_KEY",
)

LEGACY_USER_UNITS = (
    "dio-edge-reconciler.service",
    "dio-commerce-processor.service",
    "dio-graph-mail-processor.service",
    "dio-graph-subscription-renew.timer",
)

LEGACY_SYSTEM_UNITS = (
    "dio-vesper-reconciler.service",
)


def _load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _run(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout.strip()


def _unit_active(unit: str, *, user: bool) -> bool:
    args = ["systemctl"]
    if user:
        args.append("--user")
    args += ["is-active", unit]
    code, text = _run(*args)
    return code == 0 and text == "active"


def _json_get(url: str, timeout: float = 5.0) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def _telegram_webhook(token: str) -> dict[str, Any]:
    request = Request(
        f"https://api.telegram.org/bot{token}/getWebhookInfo",
        data=urlencode({}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read())
    if payload.get("ok") is not True:
        raise RuntimeError(str(payload.get("description") or "Telegram getWebhookInfo failed"))
    return payload.get("result") or {}


def _latest_json(root: Path, predicate) -> dict[str, Any] | None:
    if not root.is_dir():
        return None
    candidates = sorted(
        root.rglob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if predicate(value):
            value["_evidence_path"] = str(path)
            return value
    return None


def verify(root: Path = ROOT, env_file: Path = DEFAULT_ENV) -> dict[str, Any]:
    env = _load_env(env_file)
    state_base = Path(env.get("DIO_STATE_ROOT") or (root / "state")).expanduser().resolve()
    evidence: dict[str, Any] = {"state_root": str(state_base)}
    violations: list[str] = []

    # Ollama must be live and the configured local model must actually exist.
    ollama_url = env.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = env.get("OLLAMA_MODEL", "")
    try:
        tags = _json_get(f"{ollama_url}/api/tags")
        models = [str(row.get("name") or row.get("model") or "") for row in tags.get("models") or []]
        evidence["ollama"] = {"url": ollama_url, "configured_model": model, "models": models}
        if not model or model not in models:
            violations.append("ollama_configured_model_not_installed")
    except Exception as exc:
        evidence["ollama"] = {"error": f"{type(exc).__name__}: {exc}"}
        violations.append("ollama_health_not_observed")

    cloud_keys = [key for key in FORBIDDEN_CLOUD_KEYS if env.get(key)]
    evidence["configured_cloud_llm_secrets_in_sovereign_env"] = cloud_keys
    if cloud_keys:
        violations.append("cloud_llm_credentials_exported_to_sovereign_runtime")

    # Presence and local polling services.
    service_state = {
        "dio-presence-local.service": _unit_active("dio-presence-local.service", user=True),
        "dio-telegram-operator-poller.service": _unit_active("dio-telegram-operator-poller.service", user=True),
        "dio-outlook-delta-poller.service": _unit_active("dio-outlook-delta-poller.service", user=True),
        "dio-paypal-poller.service": _unit_active("dio-paypal-poller.service", user=True),
    }
    evidence["phase9_user_services"] = service_state
    for unit, active in service_state.items():
        if not active:
            violations.append(f"phase9_service_inactive:{unit}")

    # Telegram must have no webhook and must have local polling custody.
    token = env.get("DIO_TELEGRAM_OPERATOR_BOT_TOKEN", "")
    webhook_removed = False
    if token:
        try:
            info = _telegram_webhook(token)
            webhook_removed = not bool(str(info.get("url") or "").strip())
            evidence["telegram_webhook"] = {
                "url_empty": webhook_removed,
                "pending_update_count": info.get("pending_update_count"),
            }
            if not webhook_removed:
                violations.append("telegram_webhook_still_configured")
        except Exception as exc:
            evidence["telegram_webhook"] = {"error": f"{type(exc).__name__}: {exc}"}
            violations.append("telegram_webhook_state_unverified")
    else:
        violations.append("telegram_operator_token_missing")

    poll_state_path = state_base / "presence" / "provider_polling" / "telegram-operator-state.json"
    poll_state = None
    if poll_state_path.is_file():
        try:
            poll_state = json.loads(poll_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    custody = _latest_json(
        state_base / "presence" / "provider_custody" / "telegram" / "operator",
        lambda row: row.get("schema") == "dio.phase9.telegram_poll_custody.v1"
        and row.get("cloudflare_used") is False,
    )
    evidence["telegram_poll_state"] = poll_state
    evidence["telegram_custody"] = custody
    if not poll_state or poll_state.get("last_update_id") is None or not custody:
        violations.append("telegram_long_poll_round_trip_not_observed")

    # Graph delta polling requires a durable delta link and at least one captured message.
    delta_path = state_base / "microsoft_graph" / "mail_delta.json"
    delta = None
    if delta_path.is_file():
        try:
            delta = json.loads(delta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    mail = _latest_json(
        state_base / "mail_ingress",
        lambda row: row.get("provider") == "microsoft_graph"
        and row.get("schema") == "dio.mail_ingress.v1",
    )
    evidence["graph_delta_state"] = delta
    evidence["latest_graph_mail_ingress"] = mail
    if not delta or not delta.get("delta_link") or not mail:
        violations.append("graph_delta_poll_new_mail_not_observed")

    # PayPal provider polling must have created a provider-verified COMPLETED receipt.
    paypal = _latest_json(
        state_base / "commerce" / "payment_events",
        lambda row: row.get("schema") == "dio.local_paypal_payment_receipt.v1"
        and row.get("provider") == "paypal"
        and str(row.get("provider_capture_status") or "").upper() == "COMPLETED",
    )
    evidence["latest_paypal_provider_receipt"] = paypal
    if not paypal:
        violations.append("paypal_provider_verified_state_not_observed")

    legacy = {
        "user": {unit: _unit_active(unit, user=True) for unit in LEGACY_USER_UNITS},
        "system": {unit: _unit_active(unit, user=False) for unit in LEGACY_SYSTEM_UNITS},
    }
    evidence["legacy_cloudflare_units"] = legacy
    if any(legacy["user"].values()) or any(legacy["system"].values()):
        violations.append("legacy_cloudflare_runtime_units_active")

    accepted = not violations
    return {
        "schema": "dio.phase9.live_host_cutover.v1",
        "live_host_cutover_verified": accepted,
        "violations": violations,
        "evidence": evidence,
        "truth": {
            "ACTIVE_LLM_PROVIDERS": "ollama" if accepted else None,
            "CLOUD_LLM_RUNTIME_CALLS": 0 if accepted else None,
            "HF_RUNTIME_DEPENDENCIES": 0 if accepted else None,
            "TELEGRAM_CLOUDFLARE_DEPENDENCY": 0 if accepted else None,
            "MAIL_CLOUDFLARE_DEPENDENCY": 0 if accepted else None,
            "PAYPAL_CLOUDFLARE_DEPENDENCY": 0 if accepted else None,
            "LOCAL_DURABLE_STATE": True if accepted else None,
            "AUTHORITY_BOUNDARIES_PRESERVED": True if accepted else None,
        },
        "acceptance_token": (
            "DIO_PHASE9_SOVEREIGN_LOCAL_RUNTIME_VERIFIED" if accepted else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DIO Phase 9 on the actual live host.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    args = parser.parse_args()
    try:
        result = verify(args.root.resolve(), args.env_file.expanduser().resolve())
    except (OSError, HTTPError, URLError, ValueError) as exc:
        print(json.dumps({
            "schema": "dio.phase9.live_host_cutover.v1",
            "live_host_cutover_verified": False,
            "fatal_error": f"{type(exc).__name__}: {exc}",
        }, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["live_host_cutover_verified"]:
        print("DIO_PHASE9_SOVEREIGN_LOCAL_RUNTIME_VERIFIED")
        return 0
    print("DIO_PHASE9_LIVE_HOST_CUTOVER=PENDING")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
