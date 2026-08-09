import importlib.util
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "arda_os_grade_gate.py"
SPEC = importlib.util.spec_from_file_location("arda_os_grade_gate", MODULE_PATH)
arda_os_grade_gate = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(arda_os_grade_gate)


def _base_status() -> dict:
    return {
        "is_authoritative": True,
        "attach_verified": True,
        "is_simulation": False,
        "arm_mode": "read_only_pinned_maps",
        "enforcement_mode": "audit",
        "deny_count": 4,
        "policy_projection_state": {
            "generation_hash_prefix": 0,
            "redline_rule_count": 0,
            "projection_flags": 0,
        },
        "required_maps": {
            "maps": {
                "arda_lockdown_map": {"present": True},
                "arda_state_map": {"runtime_mode_value": 2},
            }
        },
        "phase3_measured_identity": {
            "required_maps": {
                "active_records": [],
            }
        },
        "readiness": {
            "context": {
                "enforcement_mode": "fsverity_strict",
            }
        },
    }


def test_os_grade_uses_fresh_attested_binding_for_active_generation():
    status = _base_status()
    with (
        patch.object(arda_os_grade_gate, "_secure_boot_probe", return_value={"visible": True, "enabled": True}),
        patch.object(
            arda_os_grade_gate,
            "_tpm_capture_probe",
            return_value={
                "tooling_ready": True,
                "capture_proven_live": True,
                "evidence": {
                    "software_state_binding": {
                        "available": True,
                        "bound": True,
                        "manifest_id": "measured-abc",
                        "generation": 100,
                        "policy_generation": "ARDA-POLICY-V1@1.1.0",
                        "pcr11_nonzero": True,
                    },
                    "tpm_identity": {
                        "present": True,
                        "manufacturer_rooted": True,
                    },
                },
            },
        ),
        patch.object(
            arda_os_grade_gate,
            "_policy_projection_probe",
            return_value={
                "policy_generation": "ARDA-POLICY-V1@1.1.0",
                "redline_rule_count": 2,
            },
        ),
    ):
        report = arda_os_grade_gate.build_gate_report(status)

    assert report["checks"]["measured_identity_active"] is True
    assert report["checks"]["fsverity_strict_live"] is True
    assert report["status_summary"]["active_generation"] == 100
    assert report["status_summary"]["active_manifest_id"] == "measured-abc"
    assert report["hardware_verdict"]["trust_model"] == "manufacturer_rooted_quote"


def test_os_grade_falls_back_to_projection_plan_for_policy_state():
    status = _base_status()
    with (
        patch.object(arda_os_grade_gate, "_secure_boot_probe", return_value={"visible": True, "enabled": True}),
        patch.object(
            arda_os_grade_gate,
            "_tpm_capture_probe",
            return_value={
                "tooling_ready": True,
                "capture_proven_live": True,
                "evidence": {
                    "software_state_binding": {
                        "available": True,
                        "bound": True,
                        "manifest_id": "measured-abc",
                        "generation": 100,
                        "policy_generation": "ARDA-POLICY-V1@1.1.0",
                        "pcr11_nonzero": True,
                    },
                    "tpm_identity": {
                        "present": True,
                        "manufacturer_rooted": True,
                    },
                },
            },
        ),
        patch.object(
            arda_os_grade_gate,
            "_policy_projection_probe",
            return_value={
                "policy_generation": "ARDA-POLICY-V1@1.1.0",
                "redline_rule_count": 2,
            },
        ),
    ):
        report = arda_os_grade_gate.build_gate_report(status)

    assert report["checks"]["non_empty_policy_state"] is True
    assert report["checks"]["non_empty_redline_state"] is True
    assert report["status_summary"]["policy_projection_state"]["redline_rule_count"] == 2


def test_os_grade_infers_manufacturer_rooted_identity_from_ek_chain_fields():
    status = _base_status()
    with (
        patch.object(arda_os_grade_gate, "_secure_boot_probe", return_value={"visible": True, "enabled": True}),
        patch.object(
            arda_os_grade_gate,
            "_tpm_capture_probe",
            return_value={
                "tooling_ready": True,
                "capture_proven_live": True,
                "evidence": {
                    "software_state_binding": {
                        "available": True,
                        "bound": True,
                        "manifest_id": "measured-abc",
                        "generation": 100,
                        "policy_generation": "ARDA-POLICY-V1@1.1.0",
                        "pcr11_nonzero": True,
                    },
                    "tpm_identity": {
                        "present": False,
                        "manufacturer_rooted": False,
                        "manufacturer": "Nuvoton (NTC)",
                        "ek_certificate_present": True,
                        "ak_certified_by_ek": True,
                        "identity_chain_mode": "ek-certificate+createak",
                    },
                },
            },
        ),
        patch.object(
            arda_os_grade_gate,
            "_policy_projection_probe",
            return_value={
                "policy_generation": "ARDA-POLICY-V1@1.1.0",
                "redline_rule_count": 2,
            },
        ),
    ):
        report = arda_os_grade_gate.build_gate_report(status)

    assert report["hardware_checks"]["manufacturer_rooted_tpm_identity"] is True
    assert report["hardware_verdict"]["trust_model"] == "manufacturer_rooted_quote"


def test_current_active_records_keeps_live_fsverity_records_even_if_manifest_ttl_expired():
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    status = {
        "phase3_measured_identity": {
            "required_maps": {
                "active_records": [
                    {
                        "state": "active",
                        "generation": 100,
                        "manifest_id": "measured-live",
                        "payload": {
                            "expires_at": expired,
                            "enforcement_mode": "fsverity_strict",
                        },
                    }
                ]
            }
        }
    }

    records = arda_os_grade_gate._current_active_records(status)

    assert len(records) == 1
    assert records[0]["manifest_id"] == "measured-live"


def test_remote_verifier_probe_accepts_wrapped_service_response(tmp_path):
    verdict_path = tmp_path / "latest-verdict.json"
    public_key_path = tmp_path / "verifier-key.pub.pem"

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    signed_verdict = {
        "schema_version": "arda.phase4.verifier_result.v1",
        "verdict_id": "verdict-abc",
        "verifier_id": "arda-phase4-remote-verifier",
        "manifest_id": "measured-abc",
        "manifest_digest": "sha256:" + "a" * 64,
        "attestation_timestamp": "2026-07-29T12:40:04.263439+00:00",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "ok": True,
        "production_ready": True,
        "local_attestation_passed": True,
        "externally_verifiable_attestation": True,
        "failures": [],
        "authorized_states": ["observe", "enforce"],
        "attestation_envelope_trust": {"trust_mode": "manufacturer-rooted-quote"},
        "tpm_identity": {"manufacturer": "Nuvoton (NTC)", "manufacturer_rooted": True},
        "request_digest": "sha256:" + "b" * 64,
    }
    payload = json.dumps(signed_verdict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload)
    signed_verdict["signature_algorithm"] = "ed25519"
    signed_verdict["signature"] = __import__("base64").b64encode(signature).decode("ascii")
    signed_verdict["verification_material"] = {
        "key_id": "arda-phase4-verifier",
        "public_key": __import__("base64").b64encode(public_key_path.read_bytes()).decode("ascii"),
    }
    wrapped = {
        "verifier": {"service": "arda-phase4-remote-verifier"},
        "gate": {"ok": True},
        "signed_verdict": signed_verdict,
    }
    verdict_path.write_text(json.dumps(wrapped), encoding="utf-8")

    probe = arda_os_grade_gate._remote_verifier_probe(
        str(verdict_path),
        verifier_public_key=str(public_key_path),
        verifier_key_id="arda-phase4-verifier",
    )

    assert probe["verified"] is True
    assert probe["response_wrapped"] is True
    assert probe["verdict"]["verdict_id"] == "verdict-abc"


def test_default_verifier_public_key_prefers_canonical_candidates(tmp_path):
    public_key_path = tmp_path / "verifier-key.pub.pem"
    public_key_path.write_text("pub", encoding="utf-8")

    with patch.dict(arda_os_grade_gate.os.environ, {}, clear=True):
        with patch.object(
            arda_os_grade_gate,
            "DEFAULT_VERIFIER_PUBLIC_KEY_CANDIDATES",
            (str(public_key_path),),
        ):
            assert arda_os_grade_gate._default_verifier_public_key() == str(public_key_path)
