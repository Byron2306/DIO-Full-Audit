#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_phase9_sovereign_runtime import audit as sovereign_audit  # noqa: E402

PROFILE = ROOT / "config" / "phase9_sovereign_runtime.json"
PROOFS = ROOT / "config" / "phase9_external_organ_proofs.json"
ENV_EXAMPLE = ROOT / "config" / "dio_sovereign.env.example"
INSTALLER = ROOT / "scripts" / "install_phase9_local_runtime.sh"

REQUIRED_SERVICES = (
    "dio-presence-local.service",
    "dio-telegram-operator-poller.service",
    "dio-outlook-delta-poller.service",
    "dio-paypal-poller.service",
)

FORBIDDEN_ENV_MARKERS = (
    "HF_TOKEN=",
    "OPENAI_API_KEY=",
    "GEMINI_API_KEY=",
    "GOOGLE_API_KEY=",
    "NVIDIA_API_KEY=",
    "ANTHROPIC_API_KEY=",
)

LIVE_HOST_OBLIGATIONS = (
    "ollama_health_observed",
    "cloud_llm_credentials_absent_or_unexported",
    "telegram_webhook_removed_and_long_poll_round_trip_observed",
    "graph_delta_poll_observed_new_mail",
    "paypal_provider_poll_observed_verified_state",
    "legacy_cloudflare_runtime_units_inactive",
)


class Phase9CutoverReadinessError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_static_cutover_readiness(root: Path = ROOT) -> dict[str, Any]:
    violations: list[str] = []
    base = sovereign_audit(root=root, strict_environment=False)
    if not base.get("accepted"):
        violations.extend(f"sovereign_audit:{v}" for v in base.get("violations", []))

    profile = _load_json(root / PROFILE.relative_to(ROOT))
    proofs = _load_json(root / PROOFS.relative_to(ROOT))

    if proofs.get("schema") != "dio.phase9.external_organ_proofs.v1":
        violations.append("external_organ_proof_schema_invalid")
    if proofs.get("cloud_llm_runtime_allowed") is not False:
        violations.append("external_organ_ledger_allows_cloud_llm")
    if proofs.get("hf_runtime_required") is not False:
        violations.append("external_organ_ledger_requires_hf")

    organ_pins = profile.get("organ_pins") or {}
    organ_proofs = proofs.get("organs") or {}
    for organ in ("homs", "evidex", "sophia", "nichefoundry"):
        pin = organ_pins.get(organ) or {}
        proof = organ_proofs.get(organ) or {}
        if not pin or not proof:
            violations.append(f"{organ}:missing_pin_or_proof")
            continue
        if pin.get("commit") != proof.get("commit"):
            violations.append(f"{organ}:commit_proof_mismatch")
        if pin.get("cloud_llm_allowed") is not False:
            violations.append(f"{organ}:cloud_llm_allowed")
        if organ in {"homs", "evidex"}:
            pin_proof = pin.get("proof") or {}
            if pin.get("ref") != proof.get("ref"):
                violations.append(f"{organ}:ref_proof_mismatch")
            if pin_proof.get("run_id") != proof.get("run_id"):
                violations.append(f"{organ}:run_id_proof_mismatch")
            if proof.get("conclusion") != "success":
                violations.append(f"{organ}:proof_not_success")
            if pin_proof.get("acceptance") != proof.get("acceptance"):
                violations.append(f"{organ}:acceptance_proof_mismatch")
        elif proof.get("active_llm_provider") != "ollama":
            violations.append(f"{organ}:proof_not_ollama")

    env_text = (root / ENV_EXAMPLE.relative_to(ROOT)).read_text(encoding="utf-8")
    if "DIO_PRESENCE_LLM_PROVIDER=ollama" not in env_text:
        violations.append("sovereign_env_not_ollama")
    if "OLLAMA_URL=http://127.0.0.1:11434" not in env_text:
        violations.append("sovereign_env_ollama_not_localhost")
    for marker in FORBIDDEN_ENV_MARKERS:
        if marker in env_text:
            violations.append(f"sovereign_env_contains_cloud_secret:{marker[:-1]}")

    installer = (root / INSTALLER.relative_to(ROOT)).read_text(encoding="utf-8")
    if "--telegram-cutover" not in installer:
        violations.append("installer_missing_explicit_telegram_cutover")
    if "--disable-legacy" not in installer:
        violations.append("installer_missing_explicit_legacy_disable")
    if "drop_pending_updates" not in (
        root / "scripts" / "poll_vesper_telegram.py"
    ).read_text(encoding="utf-8"):
        violations.append("telegram_cutover_does_not_preserve_pending_updates")

    systemd_root = root / "deploy" / "systemd" / "phase9"
    for service in REQUIRED_SERVICES:
        path = systemd_root / service
        if not path.is_file():
            violations.append(f"missing_service:{service}")
            continue
        text = path.read_text(encoding="utf-8")
        if "%h/.config/dio/sovereign.env" not in text:
            violations.append(f"{service}:missing_sovereign_env")

    accepted = not violations
    return {
        "schema": "dio.phase9.cutover_readiness.v1",
        "static_runtime_verified": accepted,
        "live_host_cutover_verified": False,
        "violations": violations,
        "live_host_obligations": list(LIVE_HOST_OBLIGATIONS),
        "truth": {
            "ACTIVE_LLM_PROVIDERS": "ollama" if accepted else None,
            "CLOUD_LLM_RUNTIME_CALLS": 0 if accepted else None,
            "HF_RUNTIME_DEPENDENCIES": 0 if accepted else None,
            "TELEGRAM_CLOUDFLARE_DEPENDENCY_DESIGN": 0 if accepted else None,
            "MAIL_CLOUDFLARE_DEPENDENCY_DESIGN": 0 if accepted else None,
            "PAYPAL_CLOUDFLARE_DEPENDENCY_DESIGN": 0 if accepted else None,
            "LIVE_HOST_CUTOVER_PROVEN_BY_CI": False,
        },
        "acceptance_token": (
            "DIO_PHASE9_STATIC_CUTOVER_READY" if accepted else None
        ),
    }


def main() -> int:
    result = verify_static_cutover_readiness()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["static_runtime_verified"]:
        print("DIO_PHASE9_STATIC_CUTOVER_READY")
        print("DIO_PHASE9_LIVE_HOST_CUTOVER=PENDING")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
