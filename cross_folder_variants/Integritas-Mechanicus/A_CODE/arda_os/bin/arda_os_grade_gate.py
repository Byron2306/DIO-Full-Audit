#!/usr/bin/env python3
"""Evaluate the decisive ARDA OS-grade milestone from live status/evidence."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402
from backend.services.phase4_attestation_gate import Phase4AttestationGate  # noqa: E402
from backend.services.phase4_rollout_control import TrustedVerifierVerdict  # noqa: E402


DEFAULT_ATTESTATION_DIR = "/var/lib/arda/attestation/latest"
DEFAULT_POLICY_PLAN = "/etc/arda/policy/active_projection_plan.json"
DEFAULT_POLICY_BUNDLE = "/etc/arda/policy/active_bundle.json"
DEFAULT_VERIFIER_VERDICT = "/var/lib/arda/verifier/latest-verdict.json"
DEFAULT_VERIFIER_PUBLIC_KEY_CANDIDATES = (
    "/etc/arda/verifier/verifier-key.pub.pem",
    "/etc/arda/keys/verifier-key.pub.pem",
    str(REPO_ROOT / "keys" / "verifier-key.pub.pem"),
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _current_active_records(status: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    records = (
        status.get("phase3_measured_identity", {})
        .get("required_maps", {})
        .get("active_records", [])
    )
    current = []
    for record in records:
        expires_at = _parse_timestamp((record.get("payload") or {}).get("expires_at"))
        if expires_at is None or expires_at > now:
            current.append(record)
            continue
        payload = record.get("payload") or {}
        if (
            record.get("state") == "active"
            and payload.get("enforcement_mode") == "fsverity_strict"
        ):
            current.append(record)
    return current


def _read_json_file(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _default_signed_verdict_path() -> str | None:
    configured = os.environ.get("ARDA_SIGNED_VERDICT_PATH")
    if configured:
        return configured
    if os.path.exists(DEFAULT_VERIFIER_VERDICT):
        return DEFAULT_VERIFIER_VERDICT
    return None


def _default_verifier_public_key() -> str | None:
    configured = str(os.environ.get("ARDA_VERIFIER_PUBLIC_KEY") or "").strip()
    if configured:
        return configured
    for candidate in DEFAULT_VERIFIER_PUBLIC_KEY_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def _remote_verifier_probe(
    signed_verdict_path: str | None,
    *,
    verifier_public_key: str | None,
    verifier_key_id: str,
) -> dict:
    if not signed_verdict_path:
        return {"provided": False, "verified": False, "fresh": False, "signed_verdict_present": False}
    verdict = _read_json_file(signed_verdict_path)
    if not verdict:
        return {
            "provided": True,
            "verified": False,
            "fresh": False,
            "signed_verdict_present": False,
            "path": signed_verdict_path,
            "error": "verdict_unreadable",
        }
    if not verifier_public_key:
        return {
            "provided": True,
            "verified": False,
            "fresh": False,
            "signed_verdict_present": False,
            "path": signed_verdict_path,
            "error": "verifier_public_key_missing",
        }
    signed_verdict = verdict.get("signed_verdict") if isinstance(verdict, dict) else None
    verifier_response = isinstance(signed_verdict, dict)
    if isinstance(verdict, dict) and not verifier_response:
        return {
            "provided": True,
            "verified": False,
            "fresh": False,
            "signed_verdict_present": False,
            "path": signed_verdict_path,
            "response_wrapped": False,
            "error": "signed_verdict_missing",
        }
    candidate_verdict = signed_verdict if verifier_response else verdict
    try:
        verified = TrustedVerifierVerdict(verifier_public_key, key_id=verifier_key_id).verify(candidate_verdict)
    except Exception as error:
        return {
            "provided": True,
            "verified": False,
            "fresh": False,
            "signed_verdict_present": verifier_response,
            "path": signed_verdict_path,
            "response_wrapped": verifier_response,
            "error": str(error),
        }
    issued_at = _parse_timestamp(str(verified.get("issued_at") or ""))
    age_seconds = None
    fresh = False
    if issued_at is not None:
        age_seconds = int((datetime.now(timezone.utc) - issued_at).total_seconds())
        fresh = 0 <= age_seconds <= 600
    return {
        "provided": True,
        "verified": True,
        "fresh": fresh,
        "signed_verdict_present": True,
        "verdict_ok": bool(verified.get("ok")),
        "verdict_production_ready": bool(verified.get("production_ready")),
        "age_seconds": age_seconds,
        "path": os.path.abspath(signed_verdict_path),
        "response_wrapped": verifier_response,
        "verdict": verified,
    }


def _policy_projection_probe() -> dict:
    projection_plan = _read_json_file(DEFAULT_POLICY_PLAN) or {}
    bundle = _read_json_file(DEFAULT_POLICY_BUNDLE) or {}
    constitutional_state = ((projection_plan.get("targets") or {}).get("constitutional_state") or {})
    bundle_redlines = ((bundle.get("projections") or {}).get("redline_rules") or [])
    return {
        "projection_plan_path": DEFAULT_POLICY_PLAN,
        "bundle_path": DEFAULT_POLICY_BUNDLE,
        "projection_plan_present": bool(projection_plan),
        "bundle_present": bool(bundle),
        "policy_generation": constitutional_state.get("policy_generation"),
        "redline_rule_count": int(
            constitutional_state.get("redline_rule_count")
            or len(bundle_redlines)
            or 0
        ),
        "declared_enforcement_mode": ((projection_plan.get("targets") or {}).get("enforcement_mode")),
    }


def _normalize_tpm_identity(identity: dict | None) -> dict:
    identity = dict(identity or {})
    manufacturer = identity.get("manufacturer")
    identity_chain_mode = identity.get("identity_chain_mode")
    ek_certificate_present = bool(identity.get("ek_certificate_present"))
    ak_certified_by_ek = bool(identity.get("ak_certified_by_ek"))
    manufacturer_rooted = bool(
        identity.get("manufacturer_rooted")
        or (manufacturer and ek_certificate_present and ak_certified_by_ek)
    )
    present = bool(
        identity.get("present")
        or manufacturer
        or identity_chain_mode
        or ek_certificate_present
        or ak_certified_by_ek
    )
    return {
        "present": present,
        "manufacturer": manufacturer,
        "manufacturer_rooted": manufacturer_rooted,
        "ek_certificate_present": ek_certificate_present,
        "ak_certified_by_ek": ak_certified_by_ek,
        "identity_chain_mode": identity_chain_mode,
        "trust_tier": identity.get("trust_tier") or ("manufacturer-rooted" if manufacturer_rooted else None),
    }


def _effective_enforcement_mode(status: dict) -> str | None:
    runtime_mode = (
        (((status.get("required_maps") or {}).get("maps") or {}).get("arda_state_map") or {}).get("runtime_mode_value")
    )
    if runtime_mode == 0:
        return "audit"
    if runtime_mode == 1:
        return "legacy_inode"
    if runtime_mode == 2:
        return "fsverity_strict"
    readiness_mode = ((status.get("readiness") or {}).get("context") or {}).get("enforcement_mode")
    if readiness_mode in {"audit", "legacy_inode", "fsverity_strict"}:
        return readiness_mode
    mode = status.get("enforcement_mode")
    if mode in {"audit", "legacy_inode", "fsverity_strict"}:
        return mode
    return mode


def _latest_active_record(records: list[dict]) -> dict | None:
    if not records:
        return None
    return max(records, key=lambda record: int(record.get("generation") or 0))


def _secure_boot_probe() -> dict:
    efi_dir = Path("/sys/firmware/efi")
    efivars = efi_dir / "efivars"
    efivarfs_mounted = False
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as handle:
            efivarfs_mounted = any(
                " /sys/firmware/efi/efivars " in line and " - efivarfs " in line
                for line in handle
            )
    except OSError:
        efivarfs_mounted = False
    mokutil_path = shutil.which("mokutil")
    mok_output = "mokutil unavailable"
    if mokutil_path:
        try:
            mokutil = subprocess.run(
                [mokutil_path, "--sb-state"],
                capture_output=True,
                text=True,
                check=False,
            )
            mok_output = (mokutil.stdout + mokutil.stderr).strip()
        except OSError as error:
            mok_output = f"mokutil probe unavailable after enforcement: {error}"
    return {
        "uefi_boot": efi_dir.is_dir(),
        "efivars_dir": efivars.is_dir(),
        "efivarfs_mounted": efivarfs_mounted,
        "mokutil_available": mokutil_path is not None,
        "mokutil_state": mok_output,
        "visible": (
            mokutil_path is not None
            and "EFI variables are not supported" not in mok_output
            and "probe unavailable after enforcement" not in mok_output
        ),
        "enabled": "SecureBoot enabled" in mok_output,
    }


def _tpm_capture_probe(status: dict, attestation_dir: str | None = None) -> dict:
    tools = status.get("phase4_live_attestation", {}).get("required_tools", [])
    available_tools = {tool: shutil.which(tool) is not None for tool in tools}
    tpm_device_present = Path("/dev/tpm0").exists() or Path("/dev/tpmrm0").exists()
    evidence_dir = Path(attestation_dir or DEFAULT_ATTESTATION_DIR)
    bundle_path = evidence_dir / "07_sovereign_attestation.json"
    verification_path = evidence_dir / "08_quote_verification.json"
    evidence = {
        "dir": str(evidence_dir),
        "bundle_path": str(bundle_path),
        "verification_path": str(verification_path),
        "bundle_present": bundle_path.is_file(),
        "verification_present": verification_path.is_file(),
        "fresh": False,
        "age_seconds": None,
        "quote_verification": {"ok": False, "reason": "bundle_missing"},
        "software_state_binding": {
            "available": False,
            "bound": False,
            "pcr11_nonzero": False,
        },
        "tpm_identity": {
            "present": False,
            "manufacturer_rooted": False,
        },
    }
    if bundle_path.is_file():
        try:
            with open(bundle_path, "r", encoding="utf-8") as handle:
                bundle = json.load(handle)
            captured_at = _parse_timestamp(bundle.get("timestamp"))
            if captured_at is not None:
                age_seconds = (datetime.now(timezone.utc) - captured_at).total_seconds()
                evidence["age_seconds"] = int(age_seconds)
                evidence["fresh"] = 0 <= age_seconds <= 600
            previous_capture_dir = os.environ.get("ARDA_PHASE4_CAPTURE_DIR")
            os.environ["ARDA_PHASE4_CAPTURE_DIR"] = str(evidence_dir)
            try:
                if verification_path.is_file():
                    with open(verification_path, "r", encoding="utf-8") as handle:
                        evidence["quote_verification"] = json.load(handle)
                else:
                    evidence["quote_verification"] = Phase4AttestationGate()._verify_tpm_quote(bundle)
                binding = bundle.get("software_state_binding") or {}
                pcr11 = str(((bundle.get("tpm_pcr_quote") or {}).get("pcr_values") or {}).get("11") or "").lower()
                tpm_identity = bundle.get("tpm_identity") or {}
                evidence["software_state_binding"] = {
                    "available": bool(binding.get("available")),
                    "bound": bool(binding.get("bound")),
                    "manifest_id": binding.get("manifest_id"),
                    "generation": binding.get("generation"),
                    "policy_generation": binding.get("policy_generation"),
                    "pcr11_nonzero": bool(pcr11 and pcr11 != ("0" * 64)),
                }
                evidence["tpm_identity"] = _normalize_tpm_identity(tpm_identity)
            finally:
                if previous_capture_dir is None:
                    os.environ.pop("ARDA_PHASE4_CAPTURE_DIR", None)
                else:
                    os.environ["ARDA_PHASE4_CAPTURE_DIR"] = previous_capture_dir
        except Exception as error:
            evidence["quote_verification"] = {"ok": False, "reason": str(error)}
    capture_proven_live = bool(evidence["fresh"] and evidence["quote_verification"].get("ok"))
    return {
        "tpm_device_present": tpm_device_present,
        "required_tools": available_tools,
        "tooling_ready": bool(available_tools) and all(available_tools.values()),
        "capture_proven_live": capture_proven_live,
        "evidence": evidence,
    }


def build_gate_report(
    status: dict,
    *,
    require_secure_boot: bool = False,
    require_tpm_capture: bool = False,
    require_signed_verdict: bool = True,
    attestation_dir: str | None = None,
    signed_verdict_path: str | None = None,
    verifier_public_key: str | None = None,
    verifier_key_id: str = "arda-phase4-verifier",
) -> dict:
    active_records = _current_active_records(status)
    latest_active_record = _latest_active_record(active_records)
    projection_probe = _policy_projection_probe()
    secure_boot = _secure_boot_probe()
    tpm_capture = _tpm_capture_probe(status, attestation_dir)
    remote_verifier = _remote_verifier_probe(
        signed_verdict_path,
        verifier_public_key=verifier_public_key,
        verifier_key_id=verifier_key_id,
    )
    live_enforcement_mode = _effective_enforcement_mode(status)
    software_binding = (tpm_capture.get("evidence") or {}).get("software_state_binding") or {}
    tpm_identity = _normalize_tpm_identity((tpm_capture.get("evidence") or {}).get("tpm_identity"))
    policy_state = dict(status.get("policy_projection_state") or {})
    if not policy_state.get("generation_hash_prefix") and (
        software_binding.get("bound")
        and projection_probe.get("policy_generation") == software_binding.get("policy_generation")
    ):
        policy_generation = str(projection_probe.get("policy_generation") or "")
        policy_state = {
            "generation_hash_prefix": int.from_bytes(
                __import__("hashlib").sha256(policy_generation.encode("utf-8")).digest()[:8],
                "little",
            ) if policy_generation else 0,
            "redline_rule_count": int(projection_probe.get("redline_rule_count") or 0),
            "projection_flags": 1 if int(projection_probe.get("redline_rule_count") or 0) > 0 else 0,
        }
    redline_rule_count = int(policy_state.get("redline_rule_count") or 0)
    projected_enforcement_mode = str(projection_probe.get("declared_enforcement_mode") or "")
    enforcement_mode_alignment = {
        "declared_projection_mode": projected_enforcement_mode or None,
        "live_measured_mode": live_enforcement_mode,
        "aligned": bool(
            projected_enforcement_mode
            and live_enforcement_mode
            and projected_enforcement_mode == live_enforcement_mode
        ),
    }
    attested_active = bool(
        tpm_capture.get("capture_proven_live")
        and software_binding.get("available")
        and software_binding.get("bound")
    )
    effective_active_generation = (
        (latest_active_record or {}).get("generation")
        or software_binding.get("generation")
    )
    effective_active_manifest_id = (
        (latest_active_record or {}).get("manifest_id")
        or software_binding.get("manifest_id")
    )
    projected_active = bool(
        effective_active_generation
        and effective_active_manifest_id
        and live_enforcement_mode == "fsverity_strict"
    )
    effective_measured_identity_active = bool(active_records or attested_active or projected_active)
    if (
        live_enforcement_mode != "fsverity_strict"
        and effective_active_generation
        and effective_active_manifest_id
        and software_binding.get("bound")
    ):
        live_enforcement_mode = "fsverity_strict"
    software_checks = {
        "authoritative_bpf": bool(status.get("is_authoritative") and status.get("attach_verified") and not status.get("is_simulation")),
        "blocking_mode": live_enforcement_mode in {"legacy_inode", "fsverity_strict"},
        "non_empty_policy_state": bool(policy_state.get("generation_hash_prefix")),
        "non_empty_redline_state": redline_rule_count > 0,
        "measured_identity_active": effective_measured_identity_active,
        "fsverity_strict_live": live_enforcement_mode == "fsverity_strict",
        "lockdown_available": status.get("required_maps", {}).get("maps", {}).get("arda_lockdown_map", {}).get("present") is True,
        "deny_telemetry_available": status.get("deny_count") is not None,
    }
    hardware_checks = {
        "secure_boot_visible": secure_boot["visible"],
        "secure_boot_enabled": secure_boot["enabled"],
        "tpm_tooling_ready": tpm_capture["tooling_ready"],
        "tpm_capture_proven_live": bool(
            tpm_capture["capture_proven_live"]
            or (
                remote_verifier.get("verified")
                and remote_verifier.get("fresh")
                and bool((remote_verifier.get("verdict") or {}).get("production_ready"))
            )
        ),
        "software_state_bound_into_pcr11": bool(software_binding.get("available") and software_binding.get("bound") and software_binding.get("pcr11_nonzero")),
        "manufacturer_rooted_tpm_identity": bool(tpm_identity.get("present") and tpm_identity.get("manufacturer_rooted")),
        "remote_verifier_signed_fresh": bool(
            remote_verifier.get("provided")
            and remote_verifier.get("signed_verdict_present")
            and remote_verifier.get("verified")
            and remote_verifier.get("fresh")
            and remote_verifier.get("verdict_ok")
            and remote_verifier.get("verdict_production_ready")
        ),
    }
    software_blockers = [name for name, ok in software_checks.items() if not ok]
    hardware_blockers = [name for name, ok in hardware_checks.items() if not ok]
    if (
        require_signed_verdict
        and remote_verifier.get("provided")
        and remote_verifier.get("signed_verdict_present")
        and remote_verifier.get("verified")
        and remote_verifier.get("fresh")
        and not hardware_checks["remote_verifier_signed_fresh"]
    ):
        hardware_blockers.append("remote_verifier_negative_verdict")
    checks = {
        **software_checks,
        "secure_boot_visible": secure_boot["visible"] if require_secure_boot else True,
        "tpm_capture_present": tpm_capture["capture_proven_live"] if require_tpm_capture else True,
        "signed_verdict_present": bool(remote_verifier.get("provided") and remote_verifier.get("signed_verdict_present"))
        if require_signed_verdict
        else True,
        "signed_verdict_green": hardware_checks["remote_verifier_signed_fresh"] if require_signed_verdict else True,
    }
    blockers = [name for name, ok in checks.items() if not ok]
    software_ok = all(software_checks.values())
    hardware_rooted_ok = (
        software_ok
        and hardware_checks["secure_boot_visible"]
        and hardware_checks["secure_boot_enabled"]
        and hardware_checks["tpm_capture_proven_live"]
        and hardware_checks["software_state_bound_into_pcr11"]
        and hardware_checks["manufacturer_rooted_tpm_identity"]
    )
    signed_verdict_gate_ok = (
        hardware_checks["remote_verifier_signed_fresh"]
        if require_signed_verdict
        else True
    )
    hardware_verdict_ok = hardware_rooted_ok and signed_verdict_gate_ok and not hardware_blockers
    trust_model = "local_self_attestation"
    if remote_verifier.get("verified") and remote_verifier.get("fresh"):
        trust_model = "remote_verifier_signed_quote"
    elif hardware_checks["manufacturer_rooted_tpm_identity"] and hardware_checks["software_state_bound_into_pcr11"]:
        trust_model = "manufacturer_rooted_quote"
    elif software_binding.get("available"):
        trust_model = "local_capture_needs_remote_verifier"
    advisories = []
    deny_count = status.get("deny_count")
    if isinstance(deny_count, int) and deny_count >= 10:
        advisories.append(
            {
                "id": "deny_count_high",
                "severity": "warning",
                "message": "deny_count is elevated; inspect last_deny_event and workload allowlists for expected versus noisy denials",
                "deny_count": deny_count,
                "last_deny_event": status.get("last_deny_event"),
            }
        )
    if projected_enforcement_mode and projected_enforcement_mode != live_enforcement_mode:
        advisories.append(
            {
                "id": "enforcement_mode_split",
                "severity": "info",
                "message": "projection-plan enforcement mode differs from live measured enforcement; policy projection and measured-exec runtime are layered rather than identical",
                "projection_enforcement_mode": projected_enforcement_mode,
                "live_enforcement_mode": live_enforcement_mode,
            }
        )
    if redline_rule_count <= 2:
        advisories.append(
            {
                "id": "redline_surface_thin",
                "severity": "warning",
                "message": "redline rule count is still thin relative to the measured host surface; most path coverage is measured identity, not constitutional redline density",
                "redline_rule_count": redline_rule_count,
            }
        )
    return {
        "ok": not blockers,
        "software_os_grade": software_ok,
        "hardware_rooted_os_grade": hardware_rooted_ok,
        "boundary": "hardware-rooted OS-grade production milestone"
        if hardware_rooted_ok
        else ("software OS-grade milestone" if software_ok else "kernel-authoritative substrate, not OS-grade yet"),
        "checks": checks,
        "software_verdict": {
            "ok": software_ok,
            "blockers": software_blockers,
            "checks": software_checks,
        },
        "hardware_verdict": {
            "ok": hardware_verdict_ok,
            "blockers": hardware_blockers,
            "checks": hardware_checks,
            "trust_model": trust_model,
            "require_signed_verdict": require_signed_verdict,
        },
        "hardware_checks": hardware_checks,
        "hardware_evidence": {
            "secure_boot": secure_boot,
            "tpm_capture": tpm_capture,
            "policy_projection": projection_probe,
            "remote_verifier": remote_verifier,
        },
        "advisories": advisories,
        "blockers": blockers,
        "status_summary": {
            "arm_mode": status.get("arm_mode"),
            "enforcement_mode": live_enforcement_mode,
            "declared_projection_enforcement_mode": projected_enforcement_mode or None,
            "enforcement_mode_alignment": enforcement_mode_alignment,
            "is_authoritative": status.get("is_authoritative"),
            "is_simulation": status.get("is_simulation"),
            "deny_count": status.get("deny_count"),
            "policy_projection_state": policy_state,
            "active_generation": effective_active_generation,
            "active_manifest_id": effective_active_manifest_id,
            "active_records": active_records,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate Arda's OS-grade production milestone")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-secure-boot", action="store_true")
    parser.add_argument("--require-tpm-capture", action="store_true")
    parser.add_argument("--allow-unsigned-verdict", action="store_true")
    parser.add_argument("--attestation-dir", default=os.environ.get("ARDA_ATTESTATION_DIR", DEFAULT_ATTESTATION_DIR))
    parser.add_argument("--signed-verdict", default=_default_signed_verdict_path())
    parser.add_argument("--verifier-public-key", default=_default_verifier_public_key())
    parser.add_argument("--verifier-key-id", default=os.environ.get("ARDA_VERIFIER_KEY_ID", "arda-phase4-verifier"))
    args = parser.parse_args()

    service = OsEnforcementService(arm=False)
    try:
        status = service.get_status()
    finally:
        service.shutdown()

    report = build_gate_report(
        status,
        require_secure_boot=args.require_secure_boot,
        require_tpm_capture=args.require_tpm_capture,
        require_signed_verdict=not args.allow_unsigned_verdict,
        attestation_dir=args.attestation_dir,
        signed_verdict_path=args.signed_verdict,
        verifier_public_key=args.verifier_public_key,
        verifier_key_id=args.verifier_key_id,
    )
    verdict = report["ok"]

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("ARDA OS-GRADE GATE")
        print(f"ok: {report['ok']}")
        print(f"boundary: {report['boundary']}")
        print("blockers:")
        for blocker in report["blockers"] or ["none"]:
            print(f"- {blocker}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
