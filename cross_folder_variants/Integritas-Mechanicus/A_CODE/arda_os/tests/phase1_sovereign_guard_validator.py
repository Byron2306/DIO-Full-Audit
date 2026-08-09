#!/usr/bin/env python3
"""
Phase 1 Sovereign Guard Validator

Focused validation for the current repository's Phase 1 goals:
- sovereign mode fails closed if the Ring-0 guard cannot arm
- development mode degrades to simulation instead of lying about authority
- the status surface reports the true arming posture
- the self-test surface distinguishes real authority from simulation
"""

import os
import json
import base64
import subprocess
import struct
import sys
import tempfile
import unittest
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.modules["bcc"] = MagicMock()
REPO_ROOT = Path(__file__).resolve().parents[1]

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402
from backend.services.measured_identity import (  # noqa: E402
    MeasuredIdentityVerifier,
    MeasuredProjectionGenerationStore,
)
from backend.services.attestation_service import create_envelope  # noqa: E402
from backend.services.policy_engine import generate_policy  # noqa: E402


def _write_test_sealed_bundle(
    path: Path,
    *,
    purpose: str,
    manifest_id: str,
    manifest_digest: str,
    secret_value: str,
    seal_key: str,
) -> None:
    aad = json.dumps(
        {
            "purpose": purpose,
            "manifest_id": manifest_id,
            "manifest_digest": manifest_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    key_id = "test-key-1"
    keystream = hashlib.sha256((seal_key + "|" + key_id).encode("utf-8")).digest()
    plaintext = secret_value.encode("utf-8")
    ciphertext = bytes(
        byte ^ keystream[index % len(keystream)]
        for index, byte in enumerate(plaintext)
    )
    import hmac

    path.write_text(
        json.dumps(
            {
                "schema": "arda.phase4.sealed_secret.v1",
                "purpose": purpose,
                "key_id": key_id,
                "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
                "mac_sha256": hmac.new(seal_key.encode("utf-8"), aad + b"." + ciphertext, hashlib.sha256).hexdigest(),
                "secret_fingerprint": "sha256:" + hashlib.sha256(secret_value.encode("utf-8")).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


def _with_boot_measurement(local_evidence: dict, classification: str | None = None) -> dict:
    evidence = dict(local_evidence)
    evidence["tpm_pcr_quote"] = dict(evidence.get("tpm_pcr_quote", {}))
    boot_state = classification or evidence.get("boot_state", "LAWFUL_PARTIAL")
    evidence["boot_state"] = boot_state
    pcr_values = dict(evidence.get("tpm_pcr_quote", {}).get("pcr_values", {}))
    if pcr_values.get("11") in (None, "", "0" * 64):
        pcr_values["11"] = "f" * 64
    evidence["tpm_pcr_quote"]["pcr_values"] = pcr_values
    evidence["tpm_pcr_quote"].setdefault("nonce_source", "verifier_supplied")
    evidence.setdefault(
        "software_state_binding",
        {
            "available": True,
            "bound": True,
            "manifest_id": "fixture-manifest",
            "generation": 1,
            "policy_generation": "policy-2026-07-24",
        },
    )
    evidence["boot_measurement"] = {
        "source": "test_fixture",
        "classification": boot_state,
        "secure_boot": {"available": True, "enabled": True},
        "setup_mode": {"available": True, "enabled": False},
        "lockdown": {"available": True, "value": "[integrity] confidentiality"},
        "active_lsms": {"available": True, "value": "lockdown,bpf,ima,evm"},
        "pcrs": pcr_values,
    }
    return evidence


class Phase1SovereignGuardValidator(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ["ARDA_SOVEREIGN_MODE"] = "0"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_development_mode_degrades_to_simulation(self):
        mock_bpf = sys.modules["bcc"].BPF
        mock_bpf.side_effect = Exception("bcc unavailable")

        service = OsEnforcementService("/tmp/fake_lsm.c")
        status = service.get_status()

        self.assertFalse(status["is_authoritative"])
        self.assertTrue(status["is_simulation"])
        self.assertEqual(status["arm_mode"], "simulation")
        self.assertIn("failed to arm", status["fallback_last_error"].lower())
        self.assertTrue(status["loader_attempted"])
        self.assertTrue(status["loader_last_error"])
        self.assertEqual(status["map_schema_version"], "phase5-policy-v1")
        self.assertEqual(status["enforcement_mode"], "legacy_inode")
        self.assertIn("required_maps", status)
        self.assertIn("declared_source_maps", status["required_maps"])
        self.assertIn("arda_harmony_map", status["required_maps"]["maps"])
        self.assertIsInstance(status["required_maps"]["maps"]["arda_harmony_map"]["source_declared"], bool)
        self.assertIn("phase3_measured_identity", status)
        self.assertIn("required_maps", status["phase3_measured_identity"])
        self.assertIn("arda_verity_identity_map", status["phase3_measured_identity"]["required_maps"]["maps"])
        self.assertIn("readiness", status)
        self.assertFalse(status["readiness"]["ready_for_authoritative_attempt"])
        self.assertIn("not_running_as_root", status["readiness"]["blockers"])

        mock_bpf.side_effect = None

    def test_sovereign_mode_fails_closed_on_arm_failure(self):
        os.environ["ARDA_SOVEREIGN_MODE"] = "1"
        mock_bpf = sys.modules["bcc"].BPF
        mock_bpf.side_effect = Exception("kernel context missing")

        with self.assertRaises(SystemExit):
            OsEnforcementService("/tmp/fake_lsm.c")

        mock_bpf.side_effect = None

    def test_status_and_self_test_for_authoritative_guard(self):
        mock_map = MagicMock()
        mock_map.Key = lambda inode, dev: (inode, dev)
        mock_map.Leaf = lambda value: value

        mock_bpf_instance = MagicMock()
        mock_bpf_instance.get_table.return_value = mock_map
        mock_bpf_instance.attach_lsm.return_value = None

        mock_bpf = sys.modules["bcc"].BPF
        mock_bpf.return_value = mock_bpf_instance

        service = OsEnforcementService("/tmp/fake_lsm.c")
        status = service.get_status()

        self.assertTrue(status["is_authoritative"])
        self.assertFalse(status["is_simulation"])
        self.assertTrue(status["attach_verified"])
        self.assertEqual(status["arm_mode"], "ring0")
        self.assertTrue(status["required_maps"]["all_required_present"])
        self.assertTrue(status["required_maps"]["maps"]["arda_harmony_map"]["in_process_handle"])
        self.assertIsInstance(status["required_maps"]["declared_source_maps"], list)
        self.assertTrue(status["phase3_measured_identity"]["required_maps"]["all_required_present"])
        self.assertIn("loader_status", status)
        self.assertTrue(status["loader_status"]["canonical_loader_source_exists"])
        self.assertIn("required_map_names", status["loader_status"])
        self.assertIn("phase3_required_map_names", status["loader_status"])

        with tempfile.NamedTemporaryFile() as handle:
            self_test = service.run_self_test(handle.name)

        self.assertTrue(self_test["ok"])
        self.assertTrue(self_test["checks"]["map_sync"])
        self.assertTrue(service.last_self_test["ok"])

    def test_sovereign_self_test_requires_real_authority(self):
        os.environ["ARDA_SOVEREIGN_MODE"] = "1"
        service = OsEnforcementService.__new__(OsEnforcementService)
        service.sovereign_mode = True
        service.is_authoritative = False
        service.attach_verified = False
        service.is_simulation = False
        service.lsm_map = {}
        service.last_self_test = None

        result = service.run_self_test()

        self.assertFalse(result["ok"])
        self.assertEqual(result["details"]["failure"], "ring0_guard_not_authoritative")

    def test_native_denial_self_test_requires_real_authority(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        service.is_authoritative = False
        service.attach_verified = False
        service.is_simulation = False

        result = service.run_native_denial_self_test()

        self.assertFalse(result["ok"])
        self.assertEqual(result["details"]["failure"], "ring0_guard_not_authoritative")

    def test_native_denial_self_test_reports_allowed_execution(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        service.is_authoritative = True
        service.attach_verified = True
        service.is_simulation = False

        result = service.run_native_denial_self_test()

        self.assertFalse(result["ok"])
        self.assertEqual(result["details"]["failure"], "unharmonic_binary_executed")
        self.assertEqual(result["details"]["returncode"], 0)

    def test_status_cli_reports_phase1_surface(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        cli_path = REPO_ROOT / "bin" / "arda_status.py"

        result = subprocess.run(
            [sys.executable, str(cli_path), "--json"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('"status"', result.stdout)
        self.assertIn('"arm_mode"', result.stdout)
        self.assertIn('"is_authoritative"', result.stdout)
        self.assertIn('"loader_status"', result.stdout)
        self.assertIn('"required_maps"', result.stdout)
        self.assertIn('"declared_source_maps"', result.stdout)
        self.assertIn('"phase3_measured_identity"', result.stdout)
        self.assertIn('"phase3_required_map_names"', result.stdout)
        self.assertIn('"readiness"', result.stdout)

    def test_status_cli_native_denial_path_is_reported(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        cli_path = REPO_ROOT / "bin" / "arda_status.py"

        result = subprocess.run(
            [sys.executable, str(cli_path), "--json", "--native-denial-test"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn('"native_denial_test"', result.stdout)
        self.assertIn('ring0_guard_not_authoritative', result.stdout)

    def test_phase1_root_probe_reports_phase2_map_contract_surface(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        probe_path = REPO_ROOT / "bin" / "phase1_root_probe.py"

        result = subprocess.run(
            [sys.executable, str(probe_path)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn('"phase2_map_contract_proof"', result.stdout)
        self.assertIn('"missing_required_maps"', result.stdout)
        self.assertIn('"expected_pin_paths"', result.stdout)

    def test_project_pinned_policy_requires_authoritative_ready_contract(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        service.DEFAULT_PROJECTION_SEED_PATHS = ("/bin/bash", "/usr/bin/env", "/usr/bin/python3")
        service.ENFORCEMENT_MODE_AUDIT = "audit"
        service.ENFORCEMENT_MODE_LEGACY_INODE = "legacy_inode"
        service.POLICY_PROJECTION_FLAG_REDLINE = 1
        service.enforcement_mode = "legacy_inode"
        service.is_authoritative = True
        service.get_required_map_status = lambda: {"all_required_present": True}
        projected = []
        service._update_pinned_harmony_entry = lambda path, is_harmonic: projected.append((path, is_harmonic)) or {
            "path": path,
            "harmonic": is_harmonic,
        }
        service._project_state_mode = lambda mode: mode
        service._project_policy_state = lambda policy_generation, redline_rule_count: {
            "policy_generation": policy_generation,
            "redline_rule_count": redline_rule_count,
            "generation_hash_prefix": 123,
            "projection_flags": 0 if redline_rule_count == 0 else 1,
        }
        deny_counts = iter([5, 7])
        service.get_deny_count = lambda: next(deny_counts)
        service.run_native_denial_self_test = lambda: {"ok": True, "checks": {"native_denial_observed": True}}

        with tempfile.NamedTemporaryFile() as handle:
            os.chmod(handle.name, 0o755)
            result = service.project_pinned_policy(
                [handle.name],
                enforcement_mode="legacy_inode",
                constitutional_state={"policy_generation": "ARDA-POLICY-V1@1.0.0", "redline_rule_count": 0},
                verify_native_denial_after=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["projected_count"], 1)
        self.assertEqual(result["enforcement_mode"], "legacy_inode")
        self.assertEqual(projected[0][1], True)
        self.assertEqual(result["default_seed_paths"], ["/bin/bash", "/usr/bin/env", "/usr/bin/python3"])
        self.assertEqual(result["audit"]["deny_count_before"], 5)
        self.assertEqual(result["audit"]["deny_count_after"], 7)
        self.assertEqual(result["audit"]["deny_count_delta"], 2)
        self.assertEqual(result["projected_policy_state"]["policy_generation"], "ARDA-POLICY-V1@1.0.0")
        self.assertTrue(result["native_denial_verification"]["ok"])

    def test_project_policy_cli_surfaces_authority_failure(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        cli_path = REPO_ROOT / "bin" / "arda_project_policy.py"

        result = subprocess.run(
            [sys.executable, str(cli_path), "--path", sys.executable],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot project pinned policy", result.stderr.lower())

    def test_project_policy_cli_reports_default_seed_usage(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        cli_path = REPO_ROOT / "bin" / "arda_project_policy.py"

        result = subprocess.run(
            [sys.executable, str(cli_path)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot project pinned policy", result.stderr.lower())

    def test_preflight_measured_manifest_accepts_bound_attestation(self):
        generation_db = os.path.join(tempfile.gettempdir(), "arda_test_measured_generation_accept.sqlite3")
        if os.path.exists(generation_db):
            os.unlink(generation_db)
        service = OsEnforcementService.__new__(OsEnforcementService)
        service._measured_generation_store = MeasuredProjectionGenerationStore(generation_db)
        service._measured_identity_verifier = MeasuredIdentityVerifier(service._measured_generation_store)
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "manifest-1",
            "generation": 7,
            "node_id": "node-alpha",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-1",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=120)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
            "signature": {
                "algorithm": "test-hmac",
                "keyid": "test-key",
                "signature": "deadbeef",
            },
        }
        attestation = {
            "result_id": "attestation-1",
            "subject_node_id": "node-alpha",
            "evidence_digest": "sha256:" + "a" * 64,
            "accepted": True,
            "expires_at": (now + timedelta(seconds=120)).isoformat(),
        }

        result = service.preflight_measured_manifest(manifest, attestation)

        self.assertTrue(result["ok"])
        self.assertEqual(result["enforcement_mode"], "fsverity_strict")
        self.assertEqual(result["would_stage_entry_count"], 1)
        self.assertEqual(result["loader_digest_specs"], [f"1:{'b' * 64}"])

    def test_status_prefers_pinned_runtime_mode_truth(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        service.sovereign_mode = False
        service.is_authoritative = True
        service.is_simulation = False
        service.attach_verified = True
        service.arm_mode = "ring0_loader"
        service.bpf_source = "/tmp/fake_lsm.c"
        service.pin_path = "/sys/fs/bpf/arda/harmony_map"
        service.armed_at = "2026-07-24T18:52:54+00:00"
        service.last_error = None
        service.last_self_test = None
        service.loader_attempted = True
        service.loader_last_error = None
        service.fallback_last_error = None
        service.loader_timeout_seconds = 20
        service.enforcement_mode = "legacy_inode"
        service.measured_generation_db = "/tmp/arda_measured_generation.sqlite3"
        service._measured_generation_store = MagicMock()
        service._measured_generation_store.list_records.return_value = [{"manifest_id": "phase3-root-proof-1", "state": "active"}]
        from backend.services.phase4_attestation_gate import Phase4AttestationGate
        service._phase4_attestation_gate = Phase4AttestationGate()
        service.get_loader_status = lambda: {"preferred_loader_mode": "libbpf_loader"}
        service.get_deny_count = lambda: 0
        service.assess_phase1_readiness = lambda: {"ready_for_authoritative_attempt": True, "blockers": [], "recommendations": []}
        service._inspect_declared_bpf_maps = lambda: [
            "arda_harmony_map",
            "arda_state_map",
            "arda_deny_count",
            "arda_verity_identity_map",
            "arda_active_generation_map",
        ]
        service._has_runtime_map_handle = lambda map_name: True
        service._read_state_map_mode = lambda: 2

        status = service.get_status()

        self.assertEqual(status["enforcement_mode"], "fsverity_strict")
        self.assertEqual(status["required_maps"]["enforcement_mode"], "fsverity_strict")
        self.assertEqual(status["required_maps"]["maps"]["arda_state_map"]["runtime_mode_value"], 2)
        self.assertEqual(status["phase3_measured_identity"]["required_maps"]["active_records"][0]["manifest_id"], "phase3-root-proof-1")

    def test_phase4_attestation_gate_accepts_bound_envelope_and_cloud_witness(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-gate-1",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )
        cloud_witness = {
            "claim": {"hash": manifest_digest},
            "cloud_proof": "proof-123",
            "status": "ATTESTED",
        }

        result = service.evaluate_phase4_attestation_gate(manifest, envelope, cloud_witness)

        self.assertTrue(result["ok"])
        self.assertEqual(result["manifest_digest"], manifest_digest)
        self.assertEqual(result["cloud_witness_attached"], True)

    def test_phase4_attestation_gate_rejects_bad_binding(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-gate-bad",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest="sha256:" + "d" * 64,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )
        cloud_witness = {
            "claim": {"hash": "sha256:" + "e" * 64},
            "cloud_proof": None,
            "status": "DENIED",
        }

        result = service.evaluate_phase4_attestation_gate(manifest, envelope, cloud_witness)

        self.assertFalse(result["ok"])
        self.assertIn("manifest_digest_binding", result["failures"])
        self.assertIn("cloud_witness_status", result["failures"])
        self.assertIn("cloud_witness_manifest_binding", result["failures"])

    def test_phase4_attestation_gate_accepts_real_local_evidence_bundle(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-local-evidence-ok",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-local",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        baseline_path = REPO_ROOT.parent / "evidence" / "02_pcr_values.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle))
        with open(baseline_path, "r", encoding="utf-8") as handle:
            pcr_baseline = json.load(handle)
        pcr_baseline["pcrs"]["11"] = local_evidence["tpm_pcr_quote"]["pcr_values"]["11"]
        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )

        result = service.evaluate_phase4_attestation_gate(
            manifest,
            envelope,
            local_evidence=local_evidence,
            pcr_baseline=pcr_baseline,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["local_evidence_attached"])
        self.assertEqual(result["local_evidence"]["boot_state"], "LAWFUL_PARTIAL")
        self.assertEqual(result["local_evidence"]["pcr_mismatches"], {})

    def test_phase4_attestation_gate_rejects_local_pcr_mismatch(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-local-evidence-bad",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-local",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        baseline_path = REPO_ROOT.parent / "coronation_kit" / "evidence" / "02_pcr_values.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle))
        with open(baseline_path, "r", encoding="utf-8") as handle:
            pcr_baseline = json.load(handle)
        pcr_baseline["pcrs"]["11"] = local_evidence["tpm_pcr_quote"]["pcr_values"]["11"]
        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )

        result = service.evaluate_phase4_attestation_gate(
            manifest,
            envelope,
            local_evidence=local_evidence,
            pcr_baseline=pcr_baseline,
        )

        self.assertFalse(result["ok"])
        self.assertIn("local_evidence_pcr_mismatch", result["failures"])
        self.assertIn("1", result["local_evidence"]["pcr_mismatches"])

    def test_phase4_secret_release_requires_passing_gate(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_secret_release import Phase4SecretReleaseService

        service._phase4_secret_release = Phase4SecretReleaseService()
        os.environ["ARDA_PHASE4_SEAL_KEY"] = "phase4-test-seal-key"

        with self.assertRaisesRegex(RuntimeError, "phase4 attestation gate rejected release"):
            service.release_phase4_secret(
                "policy_signing",
                {"ok": False, "manifest_id": "phase4-denied"},
                requester="root-host-phase4",
            )

    def test_phase4_secret_release_returns_fingerprint_and_token(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_secret_release import Phase4SecretReleaseService

        service._phase4_secret_release = Phase4SecretReleaseService()
        os.environ["ARDA_PHASE4_SEAL_KEY"] = "phase4-test-seal-key"
        bundle_path = Path(tempfile.gettempdir()) / "arda_phase4_policy_sealed_bundle.json"
        manifest_id = "phase4-approved"
        manifest_digest = "sha256:" + "d" * 64
        _write_test_sealed_bundle(
            bundle_path,
            purpose="policy_signing",
            manifest_id=manifest_id,
            manifest_digest=manifest_digest,
            secret_value="phase4-policy-secret",
            seal_key=os.environ["ARDA_PHASE4_SEAL_KEY"],
        )
        os.environ["ARDA_POLICY_SEALED_SECRET_BUNDLE"] = str(bundle_path)

        result = service.release_phase4_secret(
            "policy_signing",
            {
                "ok": True,
                "manifest_id": manifest_id,
                "manifest_digest": manifest_digest,
            },
            requester="root-host-phase4",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["purpose"], "policy_signing")
        self.assertEqual(result["sealed_bundle_env"], "ARDA_POLICY_SEALED_SECRET_BUNDLE")
        self.assertEqual(result["manifest_id"], manifest_id)
        self.assertTrue(result["release_token"].startswith("sha256:"))
        self.assertTrue(result["secret_fingerprint"].startswith("sha256:"))

    def test_phase4_secret_release_cli_fails_closed_without_secret(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        env.pop("ARDA_POLICY_SEALED_SECRET_BUNDLE", None)
        env["ARDA_PHASE4_SEAL_KEY"] = "phase4-test-seal-key"
        cli_path = REPO_ROOT / "bin" / "arda_phase4_secret_release.py"
        manifest_path = Path(tempfile.gettempdir()) / "arda_phase4_secret_manifest.json"
        envelope_path = Path(tempfile.gettempdir()) / "arda_phase4_secret_envelope.json"

        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-secret-cli",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-secret",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_secret_release",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        envelope_path.write_text(json.dumps(envelope), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "--manifest",
                str(manifest_path),
                "--attestation-envelope",
                str(envelope_path),
                "--purpose",
                "policy_signing",
                "--requester",
                "root-host-phase4",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sealed secret bundle not configured for purpose", result.stderr.lower())

    def test_phase4_seal_secret_cli_writes_bundle(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_PHASE4_SEAL_KEY"] = "phase4-test-seal-key"
        cli_path = REPO_ROOT / "bin" / "arda_phase4_seal_secret.py"
        output_path = Path(tempfile.gettempdir()) / "arda_phase4_sealed_cli_bundle.json"

        result = subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "--purpose",
                "policy_signing",
                "--manifest-id",
                "phase4-manifest-cli",
                "--manifest-digest",
                "sha256:" + "a" * 64,
                "--secret-value",
                "phase4-policy-secret",
                "--output",
                str(output_path),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        bundle = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sealed_bundle_env"], "ARDA_POLICY_SEALED_SECRET_BUNDLE")
        self.assertEqual(bundle["schema"], "arda.phase4.sealed_secret.v1")
        self.assertEqual(bundle["purpose"], "policy_signing")

    def test_phase5_policy_compiler_generates_signed_bundle(self):
        from backend.services.policy_compiler import compile_policy_bundle, load_and_verify_policy_bundle

        policy_path = Path(tempfile.gettempdir()) / "arda_phase5_policy.json"
        bundle_path = Path(tempfile.gettempdir()) / "arda_phase5_policy_bundle.json"
        policy = generate_policy(str(policy_path))
        bundle = compile_policy_bundle(policy)
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        verified = load_and_verify_policy_bundle(str(bundle_path))

        self.assertEqual(verified["schema_version"], "arda.policy_bundle.v1")
        self.assertEqual(verified["policy_id"], policy["policy_id"])
        self.assertIn("command_allow_index", verified["projections"])
        self.assertIn("principal_bindings", verified["projections"])
        self.assertIn("lane_bindings", verified["projections"])

    def test_phase5_policy_bundle_redline_rule_denies_before_allow(self):
        from backend.services.policy_compiler import compile_policy_bundle, evaluate_policy_bundle

        policy = {
            "policy_id": "ARDA-POLICY-V1",
            "version": "1.0.0",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "commands": [
                {
                    "name": "check_health",
                    "lanes": ["Shire"],
                    "principals": ["Magos_Indomitus"],
                }
            ],
            "redline_rules": [
                {
                    "rule_id": "deny-check-health",
                    "command": "check_health",
                    "principal": "Magos_Indomitus",
                    "lane": "Shire",
                    "reason": "temporary_constitutional_veto",
                }
            ],
        }
        bundle = compile_policy_bundle(policy)

        evaluation = evaluate_policy_bundle(
            bundle,
            command="check_health",
            principal="Magos_Indomitus",
            lane="Shire",
        )

        self.assertEqual(evaluation["decision"], "DENY")
        self.assertEqual(evaluation["decision_basis"], "redline_rule")
        self.assertEqual(evaluation["matched_rule"]["rule_id"], "deny-check-health")

    def test_phase5_compile_policy_cli_verifies_bundle(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        cli_path = REPO_ROOT / "bin" / "arda_compile_policy.py"
        policy_path = Path(tempfile.gettempdir()) / "arda_phase5_cli_policy.json"
        output_path = Path(tempfile.gettempdir()) / "arda_phase5_cli_bundle.json"
        generate_policy(str(policy_path))

        result = subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "--policy",
                str(policy_path),
                "--output",
                str(output_path),
                "--verify-after",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["verified"])
        self.assertTrue(output_path.exists())

    def test_phase5_compile_projection_plan_cli_writes_plan(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        compile_policy_cli = REPO_ROOT / "bin" / "arda_compile_policy.py"
        compile_projection_cli = REPO_ROOT / "bin" / "arda_compile_projection.py"
        policy_path = Path(tempfile.gettempdir()) / "arda_phase5_projection_policy.json"
        bundle_path = Path(tempfile.gettempdir()) / "arda_phase5_projection_bundle.json"
        plan_path = Path(tempfile.gettempdir()) / "arda_phase5_projection_plan.json"
        generate_policy(str(policy_path))

        bundle_result = subprocess.run(
            [
                sys.executable,
                str(compile_policy_cli),
                "--policy",
                str(policy_path),
                "--output",
                str(bundle_path),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(bundle_result.returncode, 0, msg=bundle_result.stderr)

        projection_result = subprocess.run(
            [
                sys.executable,
                str(compile_projection_cli),
                "--bundle",
                str(bundle_path),
                "--path",
                sys.executable,
                "--output",
                str(plan_path),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(projection_result.returncode, 0, msg=projection_result.stderr)
        payload = json.loads(projection_result.stdout)
        self.assertEqual(payload["plan"]["schema_version"], "arda.policy_projection_plan.v1")
        self.assertIn(sys.executable, payload["plan"]["targets"]["harmony_allow_paths"])
        self.assertEqual(
            payload["plan"]["targets"]["constitutional_state"]["policy_generation"],
            "ARDA-POLICY-V1@1.0.0",
        )
        self.assertTrue(plan_path.exists())

    def test_phase5_verify_policy_bundle_cli_reports_redline_deny(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        verify_cli = REPO_ROOT / "bin" / "arda_verify_policy_bundle.py"
        bundle_path = Path(tempfile.gettempdir()) / "arda_phase5_verify_bundle.json"
        from backend.services.policy_compiler import compile_policy_bundle

        bundle = compile_policy_bundle(
            {
                "policy_id": "ARDA-POLICY-V1",
                "version": "1.0.0",
                "issued_at": datetime.now(timezone.utc).isoformat(),
                "commands": [
                    {
                        "name": "check_health",
                        "lanes": ["Shire"],
                        "principals": ["Magos_Indomitus"],
                    }
                ],
                "redline_rules": [
                    {
                        "rule_id": "deny-check-health",
                        "command": "check_health",
                        "principal": "Magos_Indomitus",
                        "lane": "Shire",
                    }
                ],
            }
        )
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(verify_cli),
                "--bundle",
                str(bundle_path),
                "--command",
                "check_health",
                "--principal",
                "Magos_Indomitus",
                "--lane",
                "Shire",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["evaluation"]["decision"], "DENY")
        self.assertEqual(payload["evaluation"]["decision_basis"], "redline_rule")

    def test_phase6_unified_arda_cli_surfaces_status(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        cli_path = REPO_ROOT / "bin" / "arda"

        result = subprocess.run(
            [sys.executable, str(cli_path), "status", "--json"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("status", payload)
        self.assertIn("arm_mode", payload["status"])

    def test_phase6_deploy_artifacts_exist(self):
        deploy_root = REPO_ROOT / "deploy"
        expected_paths = [
            deploy_root / "PHASE6_OS_INTEGRATION.md",
            deploy_root / "etc" / "arda.env.example",
            deploy_root / "install_phase6_layout.sh",
            deploy_root / "systemd" / "arda-loader.service",
            deploy_root / "systemd" / "arda-policy-projection.service",
            deploy_root / "systemd" / "arda-attestation.service",
            deploy_root / "systemd" / "arda-ledger.service",
        ]

        for path in expected_paths:
            self.assertTrue(path.exists(), msg=f"missing {path}")

    def test_status_surfaces_policy_projection_state(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        service.sovereign_mode = False
        service.is_authoritative = True
        service.is_simulation = False
        service.attach_verified = True
        service.arm_mode = "ring0_loader"
        service.bpf_source = "/tmp/fake_lsm.c"
        service.pin_path = "/sys/fs/bpf/arda/harmony_map"
        service.armed_at = "2026-07-24T20:12:56+00:00"
        service.last_error = None
        service.last_self_test = None
        service.loader_attempted = True
        service.loader_last_error = None
        service.fallback_last_error = None
        service.loader_timeout_seconds = 20
        service.enforcement_mode = "audit"
        service.measured_generation_db = "/tmp/arda_measured_generation.sqlite3"
        service._measured_generation_store = MagicMock()
        service._measured_generation_store.list_records.return_value = []
        from backend.services.phase4_attestation_gate import Phase4AttestationGate
        service._phase4_attestation_gate = Phase4AttestationGate()
        service.get_loader_status = lambda: {"preferred_loader_mode": "libbpf_loader"}
        service.get_deny_count = lambda: 0
        service._read_policy_state = lambda: {
            "generation_hash_prefix": 987654321,
            "redline_rule_count": 2,
            "projection_flags": 1,
        }
        service.assess_phase1_readiness = lambda: {"ready_for_authoritative_attempt": True, "blockers": [], "recommendations": []}
        service._inspect_declared_bpf_maps = lambda: [
            "arda_harmony_map",
            "arda_state_map",
            "arda_deny_count",
            "arda_policy_state_map",
            "arda_verity_identity_map",
            "arda_active_generation_map",
        ]
        service._has_runtime_map_handle = lambda map_name: True
        service._read_state_map_mode = lambda: 0

        status = service.get_status()

        self.assertEqual(status["policy_projection_state"]["redline_rule_count"], 2)
        self.assertEqual(status["required_maps"]["maps"]["arda_policy_state_map"]["present"], True)

    def test_phase4_attestation_gate_verifies_real_tpm_quote(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-tpm-verify-ok",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-tpm",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        baseline_path = REPO_ROOT.parent / "evidence" / "02_pcr_values.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle))
        with open(baseline_path, "r", encoding="utf-8") as handle:
            pcr_baseline = json.load(handle)
        pcr_baseline["pcrs"]["11"] = local_evidence["tpm_pcr_quote"]["pcr_values"]["11"]
        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )

        result = service.evaluate_phase4_attestation_gate(
            manifest,
            envelope,
            local_evidence=local_evidence,
            pcr_baseline=pcr_baseline,
            require_tpm_quote_verification=True,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["local_evidence"]["tpm_quote_verification"]["ok"])

    def test_phase4_attestation_gate_rejects_tampered_tpm_quote_nonce(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-tpm-verify-bad",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-tpm",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        baseline_path = REPO_ROOT.parent / "evidence" / "02_pcr_values.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle))
        with open(baseline_path, "r", encoding="utf-8") as handle:
            pcr_baseline = json.load(handle)
        local_evidence["tpm_pcr_quote"]["nonce"] = "deadbeefdeadbeefdeadbeefdeadbeef"
        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )

        result = service.evaluate_phase4_attestation_gate(
            manifest,
            envelope,
            local_evidence=local_evidence,
            pcr_baseline=pcr_baseline,
            require_tpm_quote_verification=True,
        )

        self.assertFalse(result["ok"])
        self.assertIn("local_evidence_tpm_quote_verification", result["failures"])
        self.assertFalse(result["local_evidence"]["tpm_quote_verification"]["ok"])

    def test_phase4_attestation_gate_stale_envelope_drops_production_ready(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-stale-envelope",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-29",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-stale",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle))

        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-29",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )

        stale_now = now + timedelta(seconds=1200)
        result = service._phase4_attestation_gate.evaluate(
            manifest,
            envelope,
            local_evidence=local_evidence,
            require_tpm_quote_verification=False,
            require_verifier_nonce=False,
            now=stale_now,
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["local_attestation_passed"])
        self.assertFalse(result["production_ready"])
        self.assertFalse(result["externally_verifiable_attestation"])
        self.assertIn("attestation_envelope_stale", result["failures"])

    def test_phase4_attestation_gate_local_hmac_pass_is_not_production_ready(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-local-hmac-pass",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-29",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-local",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle))

        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-29",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )

        result = service._phase4_attestation_gate.evaluate(
            manifest,
            envelope,
            local_evidence=local_evidence,
            require_tpm_quote_verification=False,
            require_verifier_nonce=False,
            now=now,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["local_attestation_passed"])
        self.assertFalse(result["externally_verifiable_attestation"])
        self.assertFalse(result["production_ready"])

    def test_phase4_attestation_gate_quote_bound_envelope_is_production_ready(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-quote-bound",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-29",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-quote",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle))
        local_evidence["software_state_binding"]["manifest_digest"] = manifest_digest
        local_evidence["tpm_identity"] = {
            "ak_certified_by_ek": True,
            "ek_certificate_present": True,
            "manufacturer": "Nuvoton (NTC)",
            "identity_chain_mode": "ek-certificate+createak",
        }

        with patch("backend.services.attestation_service._get_boot_context", return_value={"secure_boot": True, "pcr0": "ok"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-29",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
                quote_bundle=local_evidence,
            )

        self.assertEqual(envelope["signing_algorithm"], "tpm-quote-manifest-v1")
        self.assertEqual(envelope["trust_mode"], "manufacturer-rooted-quote")

        with (
            patch("backend.services.attestation_service.shutil.which", return_value="/usr/bin/tpm2_checkquote"),
            patch(
                "backend.services.attestation_service.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["tpm2_checkquote"],
                    returncode=0,
                    stdout="quote ok",
                    stderr="",
                ),
            ),
        ):
            result = service._phase4_attestation_gate.evaluate(
                manifest,
                envelope,
                local_evidence=None,
                require_tpm_quote_verification=False,
                require_verifier_nonce=False,
                now=now,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["local_attestation_passed"])
        self.assertTrue(result["externally_verifiable_attestation"])
        self.assertTrue(result["production_ready"])

    def test_phase4_attestation_gate_allows_attested_only_live_proof_mode(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        service._phase4_attestation_gate = Phase4AttestationGate()
        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "phase4-proof-mode-ok",
            "generation": 1,
            "node_id": "node-phase4",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-phase4-proof",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": (now - timedelta(seconds=30)).isoformat(),
            "expires_at": (now + timedelta(seconds=240)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "b" * 64,
                    "workload_digest": "sha256:" + "c" * 64,
                }
            ],
        }
        manifest_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "schema_version": manifest["schema_version"],
                    "manifest_id": manifest["manifest_id"],
                    "generation": manifest["generation"],
                    "node_id": manifest["node_id"],
                    "policy_generation": manifest["policy_generation"],
                    "audience": manifest["audience"],
                    "attestation_result_id": manifest["attestation_result_id"],
                    "attestation_evidence_digest": manifest["attestation_evidence_digest"],
                    "issued_at": manifest["issued_at"],
                    "expires_at": manifest["expires_at"],
                    "entries": manifest["entries"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        evidence_path = REPO_ROOT.parent / "evidence" / "07_sovereign_attestation.json"
        with open(evidence_path, "r", encoding="utf-8") as handle:
            local_evidence = _with_boot_measurement(json.load(handle), "ATTESTED_ONLY")
        with patch("backend.services.attestation_service._get_boot_context", return_value={"source": "measurement_failed", "error": "missing"}):
            envelope = create_envelope(
                command="phase4_release_gate",
                principal="root-host-phase4",
                token_id="token-1",
                lane="gondor",
                policy_id="policy-2026-07-24",
                policy_version="1",
                verdict="ALLOW",
                artifact_digest=manifest_digest,
                policy_verdict="ALLOW",
                use_sigstore=False,
            )
        with patch.object(Phase4AttestationGate, "_verify_tpm_quote", return_value={"ok": True, "tool": "tpm2_checkquote"}):
            result = service.evaluate_phase4_attestation_gate(
                manifest,
                envelope,
                local_evidence=local_evidence,
                pcr_baseline=None,
                require_tpm_quote_verification=True,
                allow_attested_only_boot=True,
                allow_missing_boot_measurement_for_live_proof=True,
            )

        self.assertTrue(result["ok"])
        self.assertNotIn("boot_measurement_missing", result["failures"])
        self.assertNotIn("local_evidence_boot_state", result["failures"])

    def test_phase4_live_attestation_capture_writes_bundle(self):
        service = OsEnforcementService.__new__(OsEnforcementService)
        from backend.services.phase4_live_attestation import Phase4LiveAttestationService

        service._phase4_live_attestation = Phase4LiveAttestationService()
        temp_dir = tempfile.mkdtemp(prefix="arda-phase4-live-test-")
        real_exists = os.path.exists
        pcr11_state = {"value": "0" * 64}

        def fake_run(args, capture_output=True, text=True, check=False):
            if args[:2] in (["tpm2_getcap", "properties-fixed"], ["/usr/bin/fake", "getcap"]):
                return subprocess.CompletedProcess(args, 0, stdout="TPM2_PT_MANUFACTURER:\n  0x4E544300\n", stderr="")
            if args[:2] in (["tpm2_getcap", "handles-persistent"], ["/usr/bin/fake", "getcap"]):
                return subprocess.CompletedProcess(args, 0, stdout="0x81000001\n0x81000002\n", stderr="")
            if args[:2] in (["tpm2_pcrread", "sha256:0,1,7,11"], ["/usr/bin/fake", "pcrread"]):
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="sha256:\n  0 : 0x" + "a" * 64 + "\n  1 : 0x" + "b" * 64 + "\n  7 : 0x" + "c" * 64 + "\n  11: 0x" + pcr11_state["value"] + "\n",
                    stderr="",
                )
            if args[:2] in (["tpm2_pcrread", "sha256:11"], ["/usr/bin/fake", "pcrread"]):
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="sha256:\n  11: 0x" + pcr11_state["value"] + "\n",
                    stderr="",
                )
            if args[0] in ("tpm2_pcrextend", "/usr/bin/fake") and ("pcrextend" in args or args[0] == "tpm2_pcrextend"):
                digest_arg = next(value for value in args if ":sha256=" in value)
                digest = digest_arg.split(":sha256=", 1)[1]
                pcr11_state["value"] = hashlib.sha256((pcr11_state["value"] + digest).encode("utf-8")).hexdigest()
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[0] in ("tpm2_createprimary", "/usr/bin/fake") and ("createprimary" in args or args[0] == "tpm2_createprimary"):
                Path(args[-1]).write_bytes(b"primary")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[0] in ("tpm2_create", "/usr/bin/fake") and ("create" in args or args[0] == "tpm2_create"):
                Path(args[args.index("-u") + 1]).write_bytes(b"pub")
                Path(args[args.index("-r") + 1]).write_bytes(b"priv")
                if "--creation-data" in args:
                    Path(args[args.index("--creation-data") + 1]).write_bytes(b"creation")
                if "--creation-hash" in args:
                    Path(args[args.index("--creation-hash") + 1]).write_bytes(b"hash")
                if "--creation-ticket" in args:
                    Path(args[args.index("--creation-ticket") + 1]).write_bytes(b"ticket")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[0] in ("tpm2_load", "/usr/bin/fake") and ("load" in args or args[0] == "tpm2_load"):
                Path(args[-1]).write_bytes(b"ctx")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[0] in ("tpm2_readpublic", "/usr/bin/fake") and ("readpublic" in args or args[0] == "tpm2_readpublic"):
                Path(args[-1]).write_bytes(b"PUBLICPEM")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[0] in ("tpm2_nvreadpublic", "/usr/bin/fake") and ("nvreadpublic" in args or args[0] == "tpm2_nvreadpublic"):
                return subprocess.CompletedProcess(args, 0, stdout="NV Index public data", stderr="")
            if args[0] in ("tpm2_nvread", "/usr/bin/fake") and ("nvread" in args or args[0] == "tpm2_nvread"):
                if any("0x01c00002" == arg for arg in args):
                    output_path = next((arg for arg in args if arg.endswith(".bin")), None)
                    if output_path:
                        Path(output_path).write_bytes(b"EKCERT")
                    return subprocess.CompletedProcess(args, 0, stdout="EKCERT", stderr="")
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
            if args[0] in ("tpm2_certifycreation", "/usr/bin/fake") and ("certifycreation" in args or args[0] == "tpm2_certifycreation"):
                Path(args[args.index("-o") + 1]).write_bytes(b"ATTEST")
                Path(args[args.index("-s") + 1]).write_bytes(b"ATTESTSIG")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[0] in ("tpm2_quote", "/usr/bin/fake") and ("quote" in args or args[0] == "tpm2_quote"):
                Path(args[args.index("-m") + 1]).write_bytes(b"QUOTE")
                Path(args[args.index("-s") + 1]).write_bytes(b"SIGNATURE")
                Path(args[args.index("-o") + 1]).write_bytes(b"PCRBLOB")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            if args[0] == "/usr/bin/fake" and "-u" in args and "-m" in args and "-s" in args and "-f" in args and "-q" in args:
                return subprocess.CompletedProcess(args, 0, stdout="quote verified", stderr="")
            raise AssertionError(f"unexpected command: {args}")

        measured_boot = {
            "source": "linux_host_measurement_v1",
            "classification": "LAWFUL_PARTIAL",
            "secure_boot": {"available": True, "enabled": True},
            "setup_mode": {"available": True, "enabled": False},
            "lockdown": {"available": True, "value": "[integrity] confidentiality"},
            "active_lsms": {"available": True, "value": "lockdown,bpf,ima,evm"},
            "pcrs": {"0": "a" * 64, "1": "b" * 64, "7": "c" * 64, "11": pcr11_state["value"]},
        }

        with patch("backend.services.phase4_live_attestation.shutil.which", return_value="/usr/bin/fake"), \
             patch("backend.services.phase4_live_attestation.os.path.exists", side_effect=lambda path: True if path in {"/dev/tpm0", "/dev/tpmrm0"} else real_exists(path)), \
             patch("backend.services.phase4_live_attestation.subprocess.run", side_effect=fake_run), \
             patch("backend.services.phase4_live_attestation.measure_boot_state", return_value=measured_boot), \
             patch.object(
                 Phase4LiveAttestationService,
                 "_collect_software_state_binding",
                 return_value={
                     "available": True,
                     "bound": False,
                     "pcr_index": 11,
                     "manifest_id": "measured-test",
                     "generation": 24,
                     "policy_generation": "ARDA-POLICY-V1@1.1.0",
                     "components": [
                         {"label": "manifest_digest", "pcr_index": 11, "algorithm": "sha256", "digest": "d" * 64},
                         {"label": "policy_generation", "pcr_index": 11, "algorithm": "sha256", "digest": "e" * 64},
                     ],
                 },
             ):
            result = service.capture_phase4_live_attestation(temp_dir, nonce="abcd1234abcd1234abcd1234abcd1234")

        self.assertTrue(result["ok"])
        self.assertEqual(result["bundle"]["tpm_pcr_quote"]["nonce"], "abcd1234abcd1234abcd1234abcd1234")
        self.assertTrue(Path(result["bundle_path"]).exists())
        self.assertEqual(result["bundle"]["boot_state"], "LAWFUL_PARTIAL")
        self.assertTrue(result["bundle"]["software_state_binding"]["available"])
        self.assertTrue(result["bundle"]["software_state_binding"]["bound"])
        self.assertNotEqual(result["bundle"]["tpm_pcr_quote"]["pcr_values"]["11"], "0" * 64)
        self.assertEqual(result["bundle"]["tpm_pcr_quote"]["pcr_blob_b64"], base64.b64encode(b"PCRBLOB").decode("ascii"))
        self.assertEqual(result["bundle"]["tpm_identity"]["manufacturer"], "Nuvoton (NTC)")
        self.assertEqual(result["bundle"]["tpm_identity"]["identity_chain_mode"], "ek-certificate+ak-certification")
        self.assertTrue(result["bundle"]["tpm_identity"]["ek_certificate_present"])
        self.assertTrue(result["bundle"]["tpm_identity"]["ak_certified_by_ek"])

    def test_phase4_live_attestation_parses_tpm_manufacturer_value(self):
        from backend.services.phase4_live_attestation import Phase4LiveAttestationService

        service = Phase4LiveAttestationService()
        parsed = service._parse_tpm_manufacturer("TPM2_PT_MANUFACTURER:\n  IBM\nTPM2_PT_VENDOR_STRING_1:\n  IFX\n")
        self.assertEqual(parsed, "IBM")
        parsed_hex = service._parse_tpm_manufacturer("TPM2_PT_MANUFACTURER:\n  0x4E544300\n")
        self.assertEqual(parsed_hex, "Nuvoton (NTC)")

    def test_phase4_attestation_gate_reports_tpm_identity_trust_tier(self):
        from backend.services.phase4_attestation_gate import Phase4AttestationGate

        gate = Phase4AttestationGate()
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "measured-test",
            "generation": 28,
            "node_id": "debian",
            "policy_generation": "ARDA-POLICY-V1@1.1.0",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "ARDA-CORONATION-TEST",
            "attestation_evidence_digest": "sha256:" + "a" * 64,
            "issued_at": "2026-07-29T07:00:00+00:00",
            "expires_at": "2026-07-29T08:00:00+00:00",
            "entries": [],
        }
        envelope = create_envelope(
            command="check_health",
            principal="Magos_Indomitus",
            token_id="TOK-TEST",
            lane="Shire",
            policy_id="ARDA-POLICY-V1",
            policy_version="1.1.0",
            verdict="ALLOW",
            artifact_digest="sha256:" + "b" * 64,
            policy_verdict="ALLOW",
            use_sigstore=False,
        )
        local_evidence = {
            "boot_state": "LAWFUL_FULL",
            "boot_measurement": {"classification": "LAWFUL_FULL"},
            "chain_hash": "c" * 64,
            "file_hashes": {},
            "software_state_binding": {
                "available": True,
                "bound": True,
                "manifest_id": "measured-test",
                "generation": 28,
                "policy_generation": "ARDA-POLICY-V1@1.1.0",
            },
            "tpm_identity": {
                "manufacturer": "IBM",
                "identity_chain_mode": "endorsement-primary+ak-public",
                "ek_certificate_present": False,
                "ak_certified_by_ek": False,
            },
            "tpm_pcr_quote": {
                "nonce": "abcd" * 8,
                "nonce_source": "verifier_supplied",
                "pcr_selection": "sha256:0,1,7,11",
                "pcr_values": {"0": "a" * 64, "1": "b" * 64, "7": "c" * 64, "11": "d" * 64},
                "quote_blob_b64": base64.b64encode(b"QUOTE").decode("ascii"),
                "signature_blob_b64": base64.b64encode(b"SIG").decode("ascii"),
                "pcr_blob_b64": base64.b64encode(b"PCR").decode("ascii"),
                "ak_public_b64": base64.b64encode(b"AKPUB").decode("ascii"),
                "silicon_signed": True,
            },
        }
        with patch.object(Phase4AttestationGate, "_verify_tpm_quote", return_value={"ok": True, "tool": "tpm2_checkquote"}):
            result = gate.evaluate(
                manifest,
                envelope,
                local_evidence=local_evidence,
                require_tpm_quote_verification=True,
                require_verifier_nonce=True,
            )
        self.assertEqual(result["local_evidence"]["tpm_identity"]["trust_tier"], "identity-present-uncertified")
        self.assertFalse(result["local_evidence"]["tpm_identity"]["manufacturer_rooted"])

    def test_phase4_live_attestation_cli_requires_manifest_for_gate_verify(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        cli_path = REPO_ROOT / "bin" / "arda_phase4_live_attestation.py"

        result = subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "--output-dir",
                str(Path(tempfile.gettempdir()) / "arda_phase4_live_cli"),
                "--verify-gate",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--verify-gate requires --manifest and --attestation-envelope", result.stderr)

    def test_preflight_measured_manifest_rejects_replayed_generation(self):
        generation_db = os.path.join(tempfile.gettempdir(), "arda_test_measured_generation_replay.sqlite3")
        if os.path.exists(generation_db):
            os.unlink(generation_db)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        env["ARDA_MEASURED_GENERATION_DB"] = generation_db
        cli_path = REPO_ROOT / "bin" / "arda_preflight_measured_policy.py"

        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "manifest-replay",
            "generation": 3,
            "node_id": "node-beta",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-2",
            "attestation_evidence_digest": "sha256:" + "d" * 64,
            "issued_at": (now - timedelta(seconds=20)).isoformat(),
            "expires_at": (now + timedelta(seconds=120)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "e" * 64,
                    "workload_digest": "sha256:" + "f" * 64,
                }
            ],
            "signature": {
                "algorithm": "test-hmac",
                "keyid": "test-key",
                "signature": "cafebabe",
            },
        }
        attestation = {
            "result_id": "attestation-2",
            "subject_node_id": "node-beta",
            "evidence_digest": "sha256:" + "d" * 64,
            "accepted": True,
            "expires_at": (now + timedelta(seconds=120)).isoformat(),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            attestation_path = Path(temp_dir) / "attestation.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            attestation_path.write_text(json.dumps(attestation), encoding="utf-8")

            first = subprocess.run(
                [sys.executable, str(cli_path), "--manifest", str(manifest_path), "--attestation", str(attestation_path), "--commit-generation"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            second = subprocess.run(
                [sys.executable, str(cli_path), "--manifest", str(manifest_path), "--attestation", str(attestation_path)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn('"ok": false', second.stdout.lower())
        self.assertIn("stale or replayed", second.stderr.lower() + second.stdout.lower())

    def test_preflight_measured_manifest_cli_reports_binding_failures(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["ARDA_SOVEREIGN_MODE"] = "0"
        cli_path = REPO_ROOT / "bin" / "arda_preflight_measured_policy.py"

        now = datetime.now(timezone.utc)
        manifest = {
            "schema_version": "arda.measured_manifest.v1",
            "manifest_id": "manifest-bad-binding",
            "generation": 4,
            "node_id": "node-gamma",
            "policy_generation": "policy-2026-07-24",
            "audience": "arda-measured-preflight",
            "attestation_result_id": "attestation-3",
            "attestation_evidence_digest": "sha256:" + "1" * 64,
            "issued_at": (now - timedelta(seconds=20)).isoformat(),
            "expires_at": (now + timedelta(seconds=120)).isoformat(),
            "entries": [
                {
                    "path": sys.executable,
                    "fs_verity_algorithm_id": 1,
                    "fs_verity_digest": "2" * 64,
                    "workload_digest": "sha256:" + "3" * 64,
                }
            ],
            "signature": {
                "algorithm": "test-hmac",
                "keyid": "test-key",
                "signature": "feedface",
            },
        }
        attestation = {
            "result_id": "attestation-wrong",
            "subject_node_id": "node-other",
            "evidence_digest": "sha256:" + "4" * 64,
            "accepted": False,
            "expires_at": (now + timedelta(seconds=120)).isoformat(),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            attestation_path = Path(temp_dir) / "attestation.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            attestation_path.write_text(json.dumps(attestation), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(cli_path), "--manifest", str(manifest_path), "--attestation", str(attestation_path)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"preflight"', result.stdout)
        self.assertIn("attestation_not_accepted", result.stdout)
        self.assertIn("attestation_result_binding", result.stdout)

    def test_measured_manifest_lifecycle_stage_activate_deactivate_remove(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            generation_db = os.path.join(temp_dir, "arda_test_measured_generation_lifecycle.sqlite3")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(REPO_ROOT)
            env["ARDA_SOVEREIGN_MODE"] = "0"
            env["ARDA_MEASURED_GENERATION_DB"] = generation_db
            cli_path = REPO_ROOT / "bin" / "arda_measured_projection_lifecycle.py"

            now = datetime.now(timezone.utc)
            manifest = {
                "schema_version": "arda.measured_manifest.v1",
                "manifest_id": "manifest-life",
                "generation": 9,
                "node_id": "node-life",
                "policy_generation": "policy-2026-07-24",
                "audience": "arda-measured-preflight",
                "attestation_result_id": "attestation-life",
                "attestation_evidence_digest": "sha256:" + "7" * 64,
                "cgroup_id": "workload.slice/arda.service",
                "cgroup_kernel_id": 4242,
                "pid_namespace_inode": 111,
                "mount_namespace_inode": 222,
                "issued_at": (now - timedelta(seconds=20)).isoformat(),
                "expires_at": (now + timedelta(seconds=120)).isoformat(),
                "entries": [
                    {
                        "path": sys.executable,
                        "fs_verity_algorithm_id": 1,
                        "fs_verity_digest": "8" * 64,
                        "workload_digest": "sha256:" + "9" * 64,
                    }
                ],
                "signature": {
                    "algorithm": "test-hmac",
                    "keyid": "test-key",
                    "signature": "beadfeed",
                },
            }
            attestation = {
                "result_id": "attestation-life",
                "subject_node_id": "node-life",
                "evidence_digest": "sha256:" + "7" * 64,
                "accepted": True,
                "expires_at": (now + timedelta(seconds=120)).isoformat(),
            }

            manifest_path = Path(temp_dir) / "manifest.json"
            attestation_path = Path(temp_dir) / "attestation.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            attestation_path.write_text(json.dumps(attestation), encoding="utf-8")

            stage = subprocess.run(
                [sys.executable, str(cli_path), "stage", "--manifest", str(manifest_path), "--attestation", str(attestation_path)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            activate = subprocess.run(
                [sys.executable, str(cli_path), "activate", "--manifest-id", "manifest-life"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            deactivate = subprocess.run(
                [sys.executable, str(cli_path), "deactivate", "--manifest-id", "manifest-life", "--reason", "operator_pause"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            remove = subprocess.run(
                [sys.executable, str(cli_path), "remove", "--manifest-id", "manifest-life"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(stage.returncode, 0, msg=stage.stderr)
        self.assertIn('"action": "stage"', stage.stdout)
        self.assertIn('"state": "staged"', stage.stdout)
        self.assertEqual(activate.returncode, 0, msg=activate.stderr)
        self.assertIn('"action": "activate"', activate.stdout)
        self.assertIn('"state": "active"', activate.stdout)
        self.assertEqual(deactivate.returncode, 0, msg=deactivate.stderr)
        self.assertIn('"action": "deactivate"', deactivate.stdout)
        self.assertIn('"state": "deactivated"', deactivate.stdout)
        self.assertEqual(remove.returncode, 0, msg=remove.stderr)
        self.assertIn('"action": "remove"', remove.stdout)
        self.assertIn('"state": "removed"', remove.stdout)

    def test_measured_manifest_project_cli_fails_honestly_without_authority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            generation_db = os.path.join(temp_dir, "arda_test_measured_generation_project.sqlite3")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(REPO_ROOT)
            env["ARDA_SOVEREIGN_MODE"] = "0"
            env["ARDA_MEASURED_GENERATION_DB"] = generation_db
            cli_path = REPO_ROOT / "bin" / "arda_measured_projection_lifecycle.py"

            now = datetime.now(timezone.utc)
            manifest = {
                "schema_version": "arda.measured_manifest.v1",
                "manifest_id": "manifest-project",
                "generation": 10,
                "node_id": "node-project",
                "policy_generation": "policy-2026-07-24",
                "audience": "arda-measured-preflight",
                "attestation_result_id": "attestation-project",
                "attestation_evidence_digest": "sha256:" + "a" * 64,
                "cgroup_id": "workload.slice/arda-project.service",
                "cgroup_kernel_id": 5151,
                "pid_namespace_inode": 333,
                "mount_namespace_inode": 444,
                "issued_at": (now - timedelta(seconds=20)).isoformat(),
                "expires_at": (now + timedelta(seconds=120)).isoformat(),
                "entries": [
                    {
                        "path": sys.executable,
                        "fs_verity_algorithm_id": 1,
                        "fs_verity_digest": "b" * 64,
                        "workload_digest": "sha256:" + "c" * 64,
                    }
                ],
                "signature": {
                    "algorithm": "test-hmac",
                    "keyid": "test-key",
                    "signature": "abc12345",
                },
            }
            attestation = {
                "result_id": "attestation-project",
                "subject_node_id": "node-project",
                "evidence_digest": "sha256:" + "a" * 64,
                "accepted": True,
                "expires_at": (now + timedelta(seconds=120)).isoformat(),
            }

            manifest_path = Path(temp_dir) / "manifest.json"
            attestation_path = Path(temp_dir) / "attestation.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            attestation_path.write_text(json.dumps(attestation), encoding="utf-8")

            stage = subprocess.run(
                [sys.executable, str(cli_path), "stage", "--manifest", str(manifest_path), "--attestation", str(attestation_path)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            project = subprocess.run(
                [sys.executable, str(cli_path), "project", "--manifest-id", "manifest-project"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(stage.returncode, 0, msg=stage.stderr)
        self.assertNotEqual(project.returncode, 0)
        self.assertIn("cannot project measured manifest without authoritative ring-0 arming", project.stderr.lower())

    def test_build_verity_identity_key_matches_phase3_struct_size(self):
        digest_bytes = bytes.fromhex("bb" * 32)
        key_bytes = OsEnforcementService._build_verity_identity_key(
            cgroup_kernel_id=7001,
            generation=1,
            algorithm_id=1,
            digest_bytes=digest_bytes,
        )

        self.assertEqual(len(key_bytes), 88)
        cgroup_id, generation, algorithm_id, digest_size, digest_padded = struct.unpack(
            "<QQHH64s4x",
            key_bytes,
        )
        self.assertEqual(cgroup_id, 7001)
        self.assertEqual(generation, 1)
        self.assertEqual(algorithm_id, 1)
        self.assertEqual(digest_size, 32)
        self.assertEqual(digest_padded[:32], digest_bytes)


if __name__ == "__main__":
    unittest.main()
