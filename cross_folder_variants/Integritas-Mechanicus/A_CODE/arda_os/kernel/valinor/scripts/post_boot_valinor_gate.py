#!/usr/bin/env python3
"""Check that the host booted a Valinor kernel and restore ARDA state in-process."""

import argparse
import ctypes
import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "arda_os"))

from backend.services.attestation_service import create_envelope  # noqa: E402
from backend.services.harmonic_engine import HarmonicEngine  # noqa: E402
from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402
from backend.services.polyphonic_governance import get_polyphonic_governance_service  # noqa: E402
from backend.services.voice_registry import get_voice_registry  # noqa: E402


DEFAULT_BUNDLE = Path("/etc/arda/policy/active_bundle.json")
DEFAULT_PROJECTION_PLAN = Path("/etc/arda/policy/active_projection_plan.json")
DEFAULT_MEASURED_DIR = Path("/var/lib/arda/projection")
DEFAULT_ATTEST_DIR = Path("/var/lib/arda/attestation/latest")
DEFAULT_ATTEST_ENVELOPE = DEFAULT_ATTEST_DIR / "09_attestation_envelope.json"
DEFAULT_VERIFIER_OUTPUT = Path("/var/lib/arda/verifier/latest-verdict.json")
DEFAULT_POSTBOOT_DIAGNOSTICS = Path("/var/lib/arda/postboot/latest.json")
DEFAULT_VERIFIER_URL = "http://127.0.0.1:8094/verify/phase4"
DEFAULT_PCR_BASELINE = Path("/var/lib/arda/attestation/baselines/approved-pcr-baseline.json")
AT_FDCWD = -100


class _FileHandle(ctypes.Structure):
    _fields_ = [
        ("handle_bytes", ctypes.c_uint),
        ("handle_type", ctypes.c_int),
        ("f_handle", ctypes.c_ubyte * 128),
    ]


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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
        payload = record.get("payload") or {}
        expires_at = payload.get("expires_at")
        if not expires_at:
            current.append(record)
            continue
        try:
            parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            current.append(record)
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed.astimezone(timezone.utc) > now:
            current.append(record)
            continue
        if record.get("state") == "active" and record.get("enforcement_mode") == "fsverity_strict":
            current.append(record)
    return current


def _latest_active_record(status: dict) -> dict | None:
    records = _current_active_records(status)
    if not records:
        return None
    return max(records, key=lambda record: int(record.get("generation") or 0))


def _find_manifest_file(manifest_id: str, projection_dir: Path) -> Path | None:
    direct = projection_dir / f"{manifest_id}.json"
    candidates = [direct]
    try:
        candidates.extend(sorted(projection_dir.glob("*.json")))
    except OSError:
        pass
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        payload = _read_json(candidate)
        if payload and payload.get("manifest_id") == manifest_id:
            return candidate
    return None


def _namespace_inode(path: str) -> int | None:
    try:
        target = os.readlink(path)
    except OSError:
        return None
    if "[" not in target or not target.endswith("]"):
        return None
    try:
        return int(target.rsplit("[", 1)[1][:-1])
    except ValueError:
        return None


def _read_cgroup_path() -> str:
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
    except Exception:
        return "/"
    return lines[-1].split(":", 2)[-1] if lines else "/"


def _current_cgroup_kernel_id() -> int | None:
    cgroup_path = _read_cgroup_path()
    mount_root = "/sys/fs/cgroup"
    relative = cgroup_path.lstrip("/")
    target = os.path.join(mount_root, relative) if relative else mount_root
    libc = ctypes.CDLL(None, use_errno=True)
    handle = _FileHandle()
    handle.handle_bytes = 128
    mount_id = ctypes.c_int()
    rc = libc.name_to_handle_at(
        ctypes.c_int(AT_FDCWD),
        ctypes.c_char_p(target.encode("utf-8")),
        ctypes.byref(handle),
        ctypes.byref(mount_id),
        ctypes.c_int(0),
    )
    if rc == 0 and handle.handle_bytes >= 8:
        return int.from_bytes(bytes(handle.f_handle[:8]), "little")
    try:
        return os.stat(target).st_ino
    except OSError:
        return None


def _resolve_manifest_path(status: dict) -> Path | None:
    latest = _latest_active_record(status)
    if latest is None:
        return None
    manifest_id = str(latest.get("manifest_id") or "").strip()
    if not manifest_id:
        return None
    return _find_manifest_file(manifest_id, DEFAULT_MEASURED_DIR)


def _effective_policy_state(status: dict, projection: dict | None) -> dict:
    policy_state = dict(status.get("policy_projection_state") or {})
    if policy_state.get("generation_hash_prefix"):
        return policy_state
    projection_targets = (projection or {}).get("targets", {})
    constitutional_state = projection_targets.get("constitutional_state") or {}
    policy_generation = str(constitutional_state.get("policy_generation") or "")
    redline_rule_count = int(constitutional_state.get("redline_rule_count") or 0)
    if not policy_generation:
        return policy_state
    return {
        "generation_hash_prefix": int.from_bytes(
            hashlib.sha256(policy_generation.encode("utf-8")).digest()[:8],
            "little",
        ),
        "redline_rule_count": redline_rule_count,
        "projection_flags": 1 if redline_rule_count > 0 else 0,
    }


def _bootstrap_report(status: dict, manifest_path: Path | None) -> dict:
    bundle = _read_json(DEFAULT_BUNDLE)
    projection = _read_json(DEFAULT_PROJECTION_PLAN)
    manifest = _read_json(manifest_path) if manifest_path else None
    policy_state = _effective_policy_state(status, projection)
    active_records = _current_active_records(status)
    latest = _latest_active_record(status)
    checks = {
        "valinor_kernel": "valinor" in platform.release(),
        "policy_bundle_present": DEFAULT_BUNDLE.is_file() and bundle is not None,
        "projection_plan_present": DEFAULT_PROJECTION_PLAN.is_file() and projection is not None,
        "projection_targets_non_empty": bool(
            (projection or {}).get("targets", {}).get("harmony_allow_paths")
        ),
        "projection_mode_declared": (
            (projection or {}).get("targets", {}).get("enforcement_mode")
            in {"audit", "legacy_inode", "fsverity_strict"}
        ),
        "authoritative_maps_present": bool(status.get("required_maps", {}).get("all_required_present")),
        "policy_state_present": bool(policy_state.get("generation_hash_prefix")),
        "measured_manifest_present": bool(manifest_path and manifest_path.is_file() and manifest is not None),
        "measured_records_present": bool(active_records),
        "bpf_authoritative": bool(status.get("is_authoritative") and not status.get("is_simulation")),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not blockers,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kernel": platform.release(),
        "checks": checks,
        "blockers": blockers,
        "bundle": str(DEFAULT_BUNDLE),
        "projection_plan": str(DEFAULT_PROJECTION_PLAN),
        "manifest": str(manifest_path) if manifest_path else None,
        "status_summary": {
            "arm_mode": status.get("arm_mode"),
            "enforcement_mode": status.get("enforcement_mode"),
            "policy_projection_state": policy_state,
            "active_generation": latest.get("generation") if latest else None,
            "active_manifest_id": latest.get("manifest_id") if latest else None,
        },
    }


def _manifest_digest(manifest: dict) -> str:
    body = {
        "schema_version": manifest.get("schema_version"),
        "manifest_id": manifest.get("manifest_id"),
        "generation": manifest.get("generation"),
        "node_id": manifest.get("node_id"),
        "policy_generation": manifest.get("policy_generation"),
        "audience": manifest.get("audience"),
        "attestation_result_id": manifest.get("attestation_result_id"),
        "attestation_evidence_digest": manifest.get("attestation_evidence_digest"),
        "issued_at": manifest.get("issued_at"),
        "expires_at": manifest.get("expires_at"),
        "entries": manifest.get("entries"),
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _refresh_attestation_envelope(manifest_path: Path, evidence_bundle_path: str) -> dict:
    manifest = _read_json(manifest_path)
    bundle = _read_json(DEFAULT_BUNDLE)
    if not manifest or not bundle:
        raise RuntimeError("manifest or bundle unavailable for attestation envelope refresh")
    envelope = create_envelope(
        command="phase4_live_attestation",
        principal="root-host-phase4",
        token_id=manifest["manifest_id"],
        lane="gondor",
        policy_id=bundle["policy_id"],
        policy_version=bundle["policy_version"],
        verdict="ALLOW",
        artifact_digest=_manifest_digest(manifest),
        policy_verdict="ALLOW",
        evidence_bundle_path=evidence_bundle_path,
    )
    DEFAULT_ATTEST_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_ATTEST_ENVELOPE.write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(DEFAULT_ATTEST_ENVELOPE),
        "manifest_id": manifest["manifest_id"],
        "trust_mode": envelope.get("trust_mode"),
        "signing_algorithm": envelope.get("signing_algorithm"),
    }


def _collect_harmonic_toolchain(service: OsEnforcementService) -> list[str]:
    tool_paths: list[str] = []
    live_attestation = getattr(service, "_phase4_live_attestation", None)
    if live_attestation is not None:
        for tool in getattr(live_attestation, "REQUIRED_TOOLS", []):
            resolved = shutil.which(tool)
            if not resolved:
                continue
            if resolved not in tool_paths:
                tool_paths.append(resolved)
            real = os.path.realpath(resolved)
            if real not in tool_paths:
                tool_paths.append(real)
    for path in (sys.executable, "/usr/bin/env", "/bin/bash"):
        if path and os.path.exists(path) and path not in tool_paths:
            tool_paths.append(path)
    return tool_paths


def _project_measured_exec_toolchain(
    service: OsEnforcementService,
    *,
    active_record: dict | None,
    tool_paths: list[str],
) -> dict:
    if not active_record:
        return {
            "ok": False,
            "reason": "active_record_missing",
            "projected_exec_entries": [],
        }
    payload = active_record.get("payload") or {}
    cgroup_kernel_id = payload.get("cgroup_kernel_id")
    generation = active_record.get("generation")
    if cgroup_kernel_id is None or generation is None:
        return {
            "ok": False,
            "reason": "active_record_missing_projection_identity",
            "projected_exec_entries": [],
        }
    projected = []
    seen = set()
    for path in tool_paths:
        normalized = os.path.abspath(path)
        if normalized in seen or not os.path.exists(normalized) or not os.access(normalized, os.X_OK):
            continue
        projected.append(
            service._stage_pinned_measured_exec(  # noqa: SLF001
                cgroup_kernel_id=int(cgroup_kernel_id),
                generation=int(generation),
                path=normalized,
            )
        )
        seen.add(normalized)
    return {
        "ok": True,
        "cgroup_kernel_id": int(cgroup_kernel_id),
        "generation": int(generation),
        "projected_exec_entries": projected,
        "projected_exec_count": len(projected),
    }


def _mirror_active_generation_for_current_cgroup(
    service: OsEnforcementService,
    *,
    active_record: dict | None,
    tool_paths: list[str],
) -> dict:
    if not active_record:
        return {"ok": False, "reason": "active_record_missing"}
    payload = active_record.get("payload") or {}
    generation = active_record.get("generation")
    if generation is None:
        return {"ok": False, "reason": "active_record_missing_generation"}
    current_cgroup_kernel_id = _current_cgroup_kernel_id()
    if current_cgroup_kernel_id is None or current_cgroup_kernel_id <= 0:
        return {"ok": False, "reason": "current_cgroup_kernel_id_unavailable"}
    projected_exec_entries = []
    seen = set()
    for path in tool_paths:
        normalized = os.path.abspath(path)
        if normalized in seen or not os.path.exists(normalized) or not os.access(normalized, os.X_OK):
            continue
        projected_exec_entries.append(
            service._stage_pinned_measured_exec(  # noqa: SLF001
                cgroup_kernel_id=int(current_cgroup_kernel_id),
                generation=int(generation),
                path=normalized,
            )
        )
        seen.add(normalized)
    active_pointer = service._project_active_generation(  # noqa: SLF001
        cgroup_kernel_id=int(current_cgroup_kernel_id),
        generation=int(generation),
    )
    return {
        "ok": True,
        "source_cgroup_kernel_id": payload.get("cgroup_kernel_id"),
        "current_cgroup_kernel_id": int(current_cgroup_kernel_id),
        "generation": int(generation),
        "projected_exec_entries": projected_exec_entries,
        "projected_exec_count": len(projected_exec_entries),
        "active_generation": active_pointer,
    }


def _post_to_verifier(
    verifier_url: str,
    *,
    manifest_path: Path,
    evidence_bundle_path: str,
    pcr_baseline_path: str | None = None,
    require_verifier_nonce: bool = False,
    require_tpm_quote_verification: bool = True,
) -> dict:
    manifest_payload = _read_json_file(str(manifest_path))
    attestation_envelope_payload = _read_json_file(str(DEFAULT_ATTEST_ENVELOPE))
    evidence_bundle_payload = _read_json_file(str(evidence_bundle_path))
    quote_verification = _load_quote_verification_sidecar(evidence_bundle_path)
    if quote_verification is not None:
        evidence_bundle_payload["quote_verification"] = quote_verification
    quote_verification_path = None
    try:
        evidence_path = Path(evidence_bundle_path).expanduser().resolve()
        sidecar_path = evidence_path.parent / "08_quote_verification.json"
        if sidecar_path.is_file():
            quote_verification_path = str(sidecar_path)
    except Exception:
        quote_verification_path = None
    pcr_baseline_payload = _read_json_file(pcr_baseline_path) if pcr_baseline_path else None
    payload = {
        "manifest": manifest_payload,
        "manifest_path": str(manifest_path),
        "attestation_envelope": attestation_envelope_payload,
        "attestation_envelope_path": str(DEFAULT_ATTEST_ENVELOPE),
        "evidence_bundle": evidence_bundle_payload,
        "evidence_bundle_path": str(evidence_bundle_path),
        "quote_verification": quote_verification,
        "quote_verification_path": quote_verification_path,
        "pcr_baseline": pcr_baseline_payload,
        "pcr_baseline_path": str(pcr_baseline_path) if pcr_baseline_path else None,
        "require_verifier_nonce": require_verifier_nonce,
        "require_tpm_quote_verification": require_tpm_quote_verification,
        "allow_attested_only_boot": False,
        "allow_missing_boot_measurement_for_live_proof": False,
    }
    request = urllib.request.Request(
        verifier_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json_file(path: str) -> dict:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _load_quote_verification_sidecar(evidence_bundle_path: str) -> dict | None:
    try:
        evidence_path = Path(evidence_bundle_path).expanduser().resolve()
    except Exception:
        return None
    sidecar_path = evidence_path.parent / "08_quote_verification.json"
    if not sidecar_path.is_file():
        return None
    try:
        return json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _signer_status_from_env() -> dict:
    private_key = str(os.environ.get("ARDA_VERIFIER_PRIVATE_KEY") or "").strip()
    key_id = str(os.environ.get("ARDA_VERIFIER_KEY_ID") or "arda-phase4-verifier").strip()
    public_key = str(os.environ.get("ARDA_VERIFIER_PUBLIC_KEY") or "").strip() or None
    if not private_key:
        return {"configured": False, "enabled": False, "key_id": key_id, "error": None}
    try:
        signer = _load_signer_from_env()
    except Exception as error:
        return {"configured": True, "enabled": False, "key_id": key_id, "error": str(error)}
    payload = {
        "configured": True,
        "enabled": True,
        "key_id": key_id,
        "error": None,
    }
    if signer is not None and public_key:
        payload["public_key_b64"] = base64.b64encode(Path(public_key).read_bytes()).decode("ascii")
    return payload


def _load_signer_from_env():
    private_key = str(os.environ.get("ARDA_VERIFIER_PRIVATE_KEY") or "").strip()
    if not private_key:
        return None
    from cryptography.hazmat.primitives import serialization

    return serialization.load_pem_private_key(
        Path(private_key).read_bytes(),
        password=None,
    )


def _build_signed_verdict(result: dict, signer) -> dict | None:
    if signer is None:
        return None
    public_key = signer.public_key()
    public_bytes = public_key.public_bytes_raw()
    issued_at = datetime.now(timezone.utc).isoformat()
    authorized_states = [
        state.strip()
        for state in str(os.environ.get("ARDA_VERIFIER_AUTHORIZED_STATES", "observe,enforce,lockdown,rescue")).split(",")
        if state.strip()
    ]
    payload = {
        "schema_version": "arda.phase4.verifier_result.v1",
        "verdict_id": "verdict-" + secrets.token_hex(16),
        "verifier_id": str(os.environ.get("ARDA_VERIFIER_ID") or "arda-phase4-remote-verifier"),
        "manifest_id": result.get("manifest_id"),
        "manifest_digest": result.get("manifest_digest"),
        "attestation_timestamp": result.get("attestation_timestamp"),
        "issued_at": issued_at,
        "ok": bool(result.get("ok")),
        "production_ready": bool(result.get("production_ready")),
        "local_attestation_passed": bool(result.get("local_attestation_passed")),
        "externally_verifiable_attestation": bool(result.get("externally_verifiable_attestation")),
        "failures": list(result.get("failures") or ()),
        "authorized_states": authorized_states,
        "attestation_envelope_trust": dict(result.get("attestation_envelope_trust") or {}),
        "tpm_identity": dict((result.get("local_evidence") or {}).get("tpm_identity") or {}),
        "request_digest": "sha256:" + hashlib.sha256(
            _canonical_json_bytes(
                {
                    "manifest_id": result.get("manifest_id"),
                    "manifest_digest": result.get("manifest_digest"),
                    "attestation_timestamp": result.get("attestation_timestamp"),
                    "ok": bool(result.get("ok")),
                    "production_ready": bool(result.get("production_ready")),
                    "failures": list(result.get("failures") or ()),
                }
            )
        ).hexdigest(),
    }
    signature = signer.sign(_canonical_json_bytes(payload))
    return {
        **payload,
        "signature_algorithm": "ed25519",
        "signature": base64.b64encode(signature).decode("ascii"),
        "verification_material": {
            "key_id": str(os.environ.get("ARDA_VERIFIER_KEY_ID") or "arda-phase4-verifier"),
            "public_key": base64.b64encode(public_bytes).decode("ascii"),
        },
    }


def _signed_verdict_ready(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("signed_verdict"), dict):
        return False
    verifier = payload.get("verifier") or {}
    return bool(verifier.get("signed_verdicts_enabled"))


def _verify_and_persist_locally(
    *,
    manifest_path: Path,
    evidence_bundle_path: str,
) -> dict:
    manifest = _read_json_file(str(manifest_path))
    attestation_envelope = _read_json_file(str(DEFAULT_ATTEST_ENVELOPE))
    evidence_bundle = _read_json_file(str(evidence_bundle_path))
    quote_verification = _load_quote_verification_sidecar(evidence_bundle_path)
    if quote_verification is not None:
        evidence_bundle["quote_verification"] = quote_verification
    pcr_baseline_path = _resolve_pcr_baseline_path()
    pcr_baseline = _read_json_file(pcr_baseline_path) if pcr_baseline_path else None

    service = OsEnforcementService(arm=False)
    try:
        gate = service.evaluate_phase4_attestation_gate(
            manifest,
            attestation_envelope,
            None,
            evidence_bundle,
            pcr_baseline,
            True,
            False,
            False,
            False,
            False,
        )
    finally:
        service.shutdown()

    try:
        signer_status = _signer_status_from_env()
    except Exception as error:
        signer_status = {
            "configured": False,
            "enabled": False,
            "key_id": str(os.environ.get("ARDA_VERIFIER_KEY_ID") or "arda-phase4-verifier"),
            "error": str(error),
        }
    try:
        signer = _load_signer_from_env()
    except Exception:
        signer = None
    try:
        signed_verdict = _build_signed_verdict(gate, signer) if signer is not None else None
    except Exception:
        signed_verdict = None
    payload = {
        "verifier": {
            "service": "arda-phase4-remote-verifier",
            "verifier_id": str(os.environ.get("ARDA_VERIFIER_ID") or "arda-phase4-remote-verifier"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signed_verdicts_enabled": signer_status["enabled"],
            "signer": signer_status,
            "pcr_baseline_path": pcr_baseline_path,
        },
        "trust_summary": {
            "local_attestation_passed": gate.get("local_attestation_passed"),
            "externally_verifiable_attestation": gate.get("externally_verifiable_attestation"),
            "production_ready": gate.get("production_ready"),
            "attestation_envelope": {
                "algorithm": gate.get("attestation_envelope_trust", {}).get("algorithm"),
                "verification_mode": gate.get("attestation_envelope_trust", {}).get("verification_mode"),
                "externally_verifiable": gate.get("attestation_envelope_trust", {}).get("externally_verifiable"),
                "transparency_integrated": gate.get("attestation_envelope_trust", {}).get("transparency_integrated"),
                "trust_mode": gate.get("attestation_envelope_trust", {}).get("trust_mode"),
            },
            "tpm_identity": gate.get("local_evidence", {}).get("tpm_identity"),
        },
        "gate": gate,
        "signed_verdict": signed_verdict,
    }
    DEFAULT_VERIFIER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_VERIFIER_OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _safe_local_fallback_verdict(
    *,
    manifest_path: Path,
    evidence_bundle_path: str,
) -> dict:
    try:
        return _verify_and_persist_locally(
            manifest_path=manifest_path,
            evidence_bundle_path=evidence_bundle_path,
        )
    except Exception as error:
        manifest = _read_json(manifest_path) or {}
        fallback_payload = {
            "verifier": {
                "service": "arda-phase4-remote-verifier",
                "verifier_id": str(os.environ.get("ARDA_VERIFIER_ID") or "arda-phase4-remote-verifier"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signed_verdicts_enabled": False,
                "signer": {
                    "configured": False,
                    "enabled": False,
                    "key_id": str(os.environ.get("ARDA_VERIFIER_KEY_ID") or "arda-phase4-verifier"),
                    "error": str(error),
                },
            },
            "trust_summary": {
                "local_attestation_passed": False,
                "externally_verifiable_attestation": False,
                "production_ready": False,
                "attestation_envelope": {},
                "tpm_identity": {},
            },
            "gate": {
                "ok": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "audience": "arda-phase4-attestation-gate",
                "manifest_id": manifest.get("manifest_id"),
                "manifest_digest": None,
                "attestation_timestamp": None,
                "failures": ["local_fallback_verdict_persistence_failed"],
                "fallback_error": str(error),
                "production_ready": False,
            },
            "signed_verdict": None,
        }
        DEFAULT_VERIFIER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_VERIFIER_OUTPUT.write_text(
            json.dumps(fallback_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return fallback_payload


def _compact_project_result(project_result: dict | None) -> dict | None:
    if not project_result:
        return project_result
    return {
        "ok": bool(project_result.get("ok")),
        "skipped": bool(project_result.get("skipped")),
        "reason": project_result.get("reason"),
        "manifest_id": project_result.get("manifest_id"),
        "enforcement_mode": project_result.get("enforcement_mode"),
        "projected_entry_count": project_result.get("projected_entry_count"),
        "projected_exec_entry_count": project_result.get("projected_exec_entry_count"),
        "active_generation": project_result.get("active_generation"),
        "timestamp": project_result.get("timestamp"),
    }


def _compact_bootstrap(bootstrap: dict) -> dict:
    return {
        "ok": bool(bootstrap.get("ok")),
        "blockers": list(bootstrap.get("blockers") or []),
        "manifest": bootstrap.get("manifest"),
        "status_summary": dict(bootstrap.get("status_summary") or {}),
        "timestamp": bootstrap.get("timestamp"),
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "dict"):
        return _json_safe(value.dict())
    if hasattr(value, "__dataclass_fields__"):
        return _json_safe(asdict(value))
    return str(value)


def _harmonic_runtime_summary() -> dict:
    engine = HarmonicEngine()
    timestamps = [0.0, 200.0, 410.0, 610.0, 820.0]
    observation = None
    for idx, timestamp_ms in enumerate(timestamps):
        observation = engine.observe(
            actor_id="post_boot_gate",
            tool_name="phase4_live_attestation",
            target_domain="postboot",
            operation="phase4_live_attestation",
            environment="host",
            stage=f"sample_{idx}",
            timestamp_ms=timestamp_ms,
        )
    if observation is None:
        return {}
    return {
        "baseline_ref": observation.get("baseline_ref"),
        "timing_features": observation.get("timing_features"),
        "harmonic_state": observation.get("harmonic_state"),
    }


def _voice_runtime_summary() -> dict:
    registry = get_voice_registry()
    polyphonic = get_polyphonic_governance_service(voice_registry=registry)
    envelope = polyphonic.build_action_request_envelope(
        actor_id="root-host-phase4",
        actor_type="systemd-service",
        operation="post_boot_attestation",
        tool_name="phase4_live_attestation",
        target_domain="postboot",
    )
    polyphonic.attach_voice_profile(
        envelope,
        component_id="triune_orchestrator",
        component_type="governance",
    )
    governance = registry.resolve_voice_for_action(component_id="triune_orchestrator")
    policy = registry.resolve_voice_for_action(component_id="policy_engine")
    return {
        "governance_voice": _json_safe(governance),
        "policy_voice": _json_safe(policy),
        "attached_context": _json_safe(polyphonic.serialize_polyphonic_context(envelope)),
        "registered_voice_count": len(registry.list_voice_profiles()),
    }


def _resolve_postboot_verifier_url() -> str | None:
    configured = str(os.environ.get("ARDA_VERIFIER_URL") or "").strip()
    if configured.lower() in {"off", "disable", "disabled", "none"}:
        return None
    if configured:
        return configured
    use_loopback = str(os.environ.get("ARDA_POSTBOOT_USE_LOOPBACK_VERIFIER", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if use_loopback:
        return DEFAULT_VERIFIER_URL
    return None


def _resolve_pcr_baseline_path() -> str | None:
    configured = str(os.environ.get("ARDA_PCR_BASELINE_PATH") or "").strip()
    if configured:
        return configured
    if DEFAULT_PCR_BASELINE.is_file():
        return str(DEFAULT_PCR_BASELINE)
    return None


def _wait_unit_names() -> list[str]:
    raw = str(os.environ.get("ARDA_POSTBOOT_WAIT_FOR_UNITS") or "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _systemctl_active_state(unit: str) -> str:
    if not shutil.which("systemctl"):
        return "unknown"
    proc = subprocess.run(
        ["systemctl", "show", unit, "--property=ActiveState", "--value"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return "unknown"
    return proc.stdout.strip() or "unknown"


def _wait_for_boot_units() -> dict[str, Any]:
    units = _wait_unit_names()
    if not units:
        return {
            "enabled": False,
            "ok": True,
            "units": [],
            "states": {},
            "waited_seconds": 0.0,
        }
    timeout = float(str(os.environ.get("ARDA_POSTBOOT_WAIT_TIMEOUT_SECONDS") or "45").strip())
    poll = float(str(os.environ.get("ARDA_POSTBOOT_WAIT_POLL_SECONDS") or "1").strip())
    start = time.monotonic()
    deadline = start + max(timeout, 0.0)
    states = {unit: _systemctl_active_state(unit) for unit in units}
    while time.monotonic() < deadline:
        if all(state == "active" for state in states.values()):
            break
        time.sleep(max(poll, 0.1))
        states = {unit: _systemctl_active_state(unit) for unit in units}
    waited = round(time.monotonic() - start, 3)
    return {
        "enabled": True,
        "ok": all(state == "active" for state in states.values()),
        "units": units,
        "states": states,
        "waited_seconds": waited,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Valinor post-boot gate")
    parser.add_argument("--require-arda-gate", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    kernel = platform.release()
    valinor_kernel = "valinor" in kernel
    try:
        lsm_text = Path("/sys/kernel/security/lsm").read_text(encoding="utf-8").strip()
        lsm_code = 0
    except Exception as exc:
        lsm_text = str(exc)
        lsm_code = 1

    arda_gate = None
    if args.require_arda_gate:
        os.environ["ARDA_SOVEREIGN_MODE"] = "1"
        boot_unit_wait = _wait_for_boot_units()
        strict_value = str(os.environ.get("ARDA_POSTBOOT_REQUIRE_VERIFIER", "1")).strip().lower()
        strict_verifier = strict_value not in {"0", "false", "no", "off"}
        allow_local_fallback = str(os.environ.get("ARDA_POSTBOOT_ALLOW_LOCAL_FALLBACK", "0")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        live_media_mode = str(os.environ.get("ARDA_POSTBOOT_LIVE_MEDIA", "0")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        promote_strict = str(os.environ.get("ARDA_POSTBOOT_PROMOTE_STRICT", "0")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        service = OsEnforcementService()
        try:
            status_after_arm = service.get_status()
            latest = _latest_active_record(status_after_arm)
            manifest_id = latest.get("manifest_id") if latest else None
            project_result = None
            project_error = None
            if manifest_id and promote_strict:
                try:
                    project_result = service.project_staged_measured_manifest(manifest_id)
                except Exception as error:
                    project_error = str(error)
            elif manifest_id:
                project_result = {
                    "ok": True,
                    "skipped": True,
                    "reason": "ARDA_POSTBOOT_PROMOTE_STRICT is not enabled",
                    "manifest_id": manifest_id,
                    "enforcement_mode": service.get_status().get("enforcement_mode"),
                }
            status_after_project = service.get_status()
            manifest_path = _resolve_manifest_path(status_after_project)
            bootstrap = _bootstrap_report(status_after_project, manifest_path)
            live_media_parity_ok = (
                live_media_mode
                and valinor_kernel
                and boot_unit_wait["ok"]
                and bool(status_after_project.get("is_authoritative"))
                and not bool(status_after_project.get("is_simulation"))
            )

            verifier_url = _resolve_postboot_verifier_url()
            attestation_result = {
                "returncode": 0,
                "output": "automatic post-boot attestation not configured",
                "verifier_url": verifier_url or None,
            }
            if bootstrap["ok"] and verifier_url and manifest_path is not None:
                attestation_context = {
                    "harmonized_toolchain_paths": [],
                    "harmonize_result": None,
                    "measured_toolchain_result": None,
                    "current_cgroup_projection": None,
                    "last_deny_event": None,
                    "capture_bundle_path": None,
                    "refreshed_attestation_envelope": None,
                    "verifier_output": str(DEFAULT_VERIFIER_OUTPUT),
                }
                try:
                    nonce = secrets.token_hex(16)
                    harmonized_paths = _collect_harmonic_toolchain(service)
                    attestation_context["harmonized_toolchain_paths"] = harmonized_paths
                    harmonize_result = None
                    if harmonized_paths:
                        harmonize_result = service.project_pinned_policy(
                            harmonic_paths=harmonized_paths,
                            enforcement_mode=service.enforcement_mode,
                        )
                    attestation_context["harmonize_result"] = harmonize_result
                    measured_toolchain_result = _project_measured_exec_toolchain(
                        service,
                        active_record=latest,
                        tool_paths=harmonized_paths,
                    )
                    attestation_context["measured_toolchain_result"] = measured_toolchain_result
                    current_cgroup_projection = _mirror_active_generation_for_current_cgroup(
                        service,
                        active_record=latest,
                        tool_paths=harmonized_paths,
                    )
                    attestation_context["current_cgroup_projection"] = current_cgroup_projection
                    capture = service.capture_phase4_live_attestation(str(DEFAULT_ATTEST_DIR), nonce=nonce)
                    attestation_context["last_deny_event"] = service.get_last_deny_event()
                    attestation_context["capture_bundle_path"] = capture["bundle_path"]
                    refreshed = _refresh_attestation_envelope(manifest_path, capture["bundle_path"])
                    attestation_context["refreshed_attestation_envelope"] = refreshed
                    verifier_response = _post_to_verifier(
                        verifier_url,
                        manifest_path=manifest_path,
                        evidence_bundle_path=capture["bundle_path"],
                        pcr_baseline_path=_resolve_pcr_baseline_path(),
                        require_verifier_nonce=False,
                    )
                    if strict_verifier and not _signed_verdict_ready(verifier_response):
                        raise RuntimeError("verifier response missing signed verdict")
                    DEFAULT_VERIFIER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
                    DEFAULT_VERIFIER_OUTPUT.write_text(
                        json.dumps(verifier_response, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    attestation_result = {
                        "returncode": 0,
                        "output": json.dumps(
                            attestation_context,
                            sort_keys=True,
                        ),
                        "verifier_url": verifier_url,
                    }
                except urllib.error.HTTPError as error:
                    attestation_context["last_deny_event"] = service.get_last_deny_event()
                    try:
                        detail = error.read().decode("utf-8", errors="replace")
                    except Exception:
                        detail = ""
                    fallback_payload = None
                    if allow_local_fallback:
                        fallback_payload = _safe_local_fallback_verdict(
                            manifest_path=manifest_path,
                            evidence_bundle_path=capture["bundle_path"],
                        )
                    attestation_result = {
                        "returncode": 0 if (fallback_payload and fallback_payload.get("gate", {}).get("ok") and not strict_verifier) else 1,
                        "output": json.dumps(
                            {
                                "error": f"verifier service rejected request: HTTP {error.code}",
                                "detail": detail,
                                "fallback_persisted": bool(fallback_payload),
                                "fallback_manifest_id": (fallback_payload or {}).get("gate", {}).get("manifest_id"),
                                "context": attestation_context,
                            },
                            sort_keys=True,
                        ),
                        "verifier_url": verifier_url,
                    }
                except urllib.error.URLError as error:
                    attestation_context["last_deny_event"] = service.get_last_deny_event()
                    fallback_payload = None
                    if allow_local_fallback:
                        fallback_payload = _safe_local_fallback_verdict(
                            manifest_path=manifest_path,
                            evidence_bundle_path=capture["bundle_path"],
                        )
                    attestation_result = {
                        "returncode": 0 if (fallback_payload and fallback_payload.get("gate", {}).get("ok") and not strict_verifier) else 1,
                        "output": json.dumps(
                            {
                                "error": f"verifier service unavailable: {error}",
                                "fallback_persisted": bool(fallback_payload),
                                "fallback_manifest_id": (fallback_payload or {}).get("gate", {}).get("manifest_id"),
                                "context": attestation_context,
                            },
                            sort_keys=True,
                        ),
                        "verifier_url": verifier_url,
                    }
                except Exception as error:
                    attestation_context["last_deny_event"] = service.get_last_deny_event()
                    attestation_result = {
                        "returncode": 1,
                        "output": json.dumps(
                            {
                                "error": str(error),
                                "context": attestation_context,
                            },
                            sort_keys=True,
                        ),
                        "verifier_url": verifier_url,
                    }

            diagnostics = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "kernel": kernel,
                "manifest_id": manifest_id,
                "boot_unit_wait": boot_unit_wait,
                "bootstrap": bootstrap,
                "harmonic_runtime": _harmonic_runtime_summary(),
                "voice_runtime": _voice_runtime_summary(),
                "measured_project": {
                    "ok": project_error is None,
                    "promote_strict": promote_strict,
                    "manifest_id": manifest_id,
                    "error": project_error,
                    "result": _compact_project_result(project_result),
                },
                "live_attestation": attestation_result,
                "strict_verifier": strict_verifier,
                "allow_local_fallback": allow_local_fallback,
                "promote_strict": promote_strict,
                "live_media_mode": live_media_mode,
                "live_media_parity_ok": live_media_parity_ok,
            }
            DEFAULT_POSTBOOT_DIAGNOSTICS.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_POSTBOOT_DIAGNOSTICS.write_text(
                json.dumps(_json_safe(diagnostics), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            arda_gate = {
                "ok": (
                    (bootstrap["ok"] or live_media_parity_ok)
                    and project_error is None
                    and (
                        attestation_result["returncode"] == 0
                        or not verifier_url
                        or not strict_verifier
                    )
                ),
                "status": {
                    "returncode": 0,
                    "output": json.dumps(
                        {
                            "arm_mode": status_after_project.get("arm_mode"),
                            "is_authoritative": status_after_project.get("is_authoritative"),
                            "attach_verified": status_after_project.get("attach_verified"),
                        },
                        sort_keys=True,
                    ),
                },
                "measured_project": {
                    "returncode": 0 if project_error is None else 1,
                    "output": project_error or json.dumps(_compact_project_result(project_result) or {}, sort_keys=True),
                    "manifest_id": manifest_id,
                },
                "bootstrap": {
                    "returncode": 0 if bootstrap["ok"] else 1,
                    "output": json.dumps(_compact_bootstrap(bootstrap), sort_keys=True),
                },
                "live_media": {
                    "enabled": live_media_mode,
                    "parity_ok": live_media_parity_ok,
                    "host_grade_measured_boot": bootstrap["ok"],
                    "host_grade_note": (
                        "live media parity passed; host-grade measured manifest/TPM attestation "
                        "requires installation or a QEMU vTPM/Secure Boot lane"
                        if live_media_mode and live_media_parity_ok and not bootstrap["ok"]
                        else None
                    ),
                },
                "harmonic_runtime": diagnostics["harmonic_runtime"],
                "voice_runtime": diagnostics["voice_runtime"],
                "live_attestation": attestation_result,
                "warnings": [
                    "live_media_host_grade_attestation_unavailable"
                    if live_media_mode and live_media_parity_ok and not bootstrap["ok"]
                    else None,
                    "postboot_live_attestation_failed"
                    if verifier_url and attestation_result["returncode"] != 0
                    else None,
                    "postboot_verifier_not_configured" if not verifier_url else None,
                    "postboot_unsigned_fallback_disallowed"
                    if strict_verifier and not allow_local_fallback and verifier_url and attestation_result["returncode"] != 0
                    else None,
                ],
                "diagnostics_path": str(DEFAULT_POSTBOOT_DIAGNOSTICS),
            }
            arda_gate["warnings"] = [warning for warning in arda_gate["warnings"] if warning]
        finally:
            service.shutdown()

    checks = {
        "valinor_kernel": valinor_kernel,
        "bpf_lsm_active": lsm_code == 0 and "bpf" in lsm_text.split(","),
        "arda_gate": True if arda_gate is None else arda_gate["ok"],
    }
    blockers = [name for name, ok in checks.items() if not ok]
    report = {
        "ok": not blockers,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kernel": kernel,
        "checks": checks,
        "blockers": blockers,
        "active_lsms": lsm_text,
        "arda_gate": arda_gate,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("VALINOR POST-BOOT GATE")
        print(f"ok: {report['ok']}")
        print(f"kernel: {kernel}")
        print("blockers:")
        for blocker in blockers or ["none"]:
            print(f"- {blocker}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
