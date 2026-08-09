#!/usr/bin/env python3
"""Promote a live Arda host toward the OS-grade gate in one ordered operation."""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
PYTHON = sys.executable
DEFAULT_GENERATION_DB = "/var/lib/arda/projection/arda_measured_generation.sqlite3"
DEFAULT_ATTESTATION_DIR = "/var/lib/arda/attestation/latest"
DEFAULT_ENVELOPE_PATH_NAME = "09_attestation_envelope.json"

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402
from backend.services.attestation_service import create_envelope, should_use_sigstore  # noqa: E402


_GATE_SPEC = importlib.util.spec_from_file_location(
    "arda_os_grade_gate",
    REPO_ROOT / "bin" / "arda_os_grade_gate.py",
)
if _GATE_SPEC is None or _GATE_SPEC.loader is None:
    raise RuntimeError("unable to load OS-grade gate module")
_GATE_MODULE = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(_GATE_MODULE)
build_gate_report = _GATE_MODULE.build_gate_report


def _run(script_name: str, args: list[str]) -> tuple[int, dict | None, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    env.setdefault("ARDA_MEASURED_GENERATION_DB", "/var/lib/arda/projection/arda_measured_generation.sqlite3")
    result = subprocess.run(
        [PYTHON, str(REPO_ROOT / "bin" / script_name), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            parsed = None
    return result.returncode, parsed, (result.stdout + result.stderr).strip()


def _manifest_id(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)["manifest_id"]


def _next_generation(node_id: str, db_path: str) -> int:
    try:
        from backend.services.measured_identity import MeasuredProjectionGenerationStore

        store = MeasuredProjectionGenerationStore(db_path)
        try:
            return store.next_generation(node_id)
        finally:
            store.close()
    except Exception:
        return 1


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _attestation_binding(attestation_dir: str) -> dict:
    bundle_path = os.path.join(attestation_dir, "07_sovereign_attestation.json")
    if not os.path.exists(bundle_path):
        return {}
    bundle = _read_json(bundle_path)
    chain_hash = str(bundle.get("chain_hash") or "").strip().lower()
    mirror_id = str(bundle.get("mirror_id") or "").strip()
    payload = {}
    if mirror_id:
        payload["attestation_result_id"] = mirror_id
    if chain_hash:
        payload["attestation_evidence_digest"] = f"sha256:{chain_hash}"
    payload["attestation_bundle_path"] = bundle_path
    return payload


def _manifest_digest(manifest: dict) -> str:
    import hashlib

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


def _write_attestation_envelope(*, manifest: dict, bundle: dict, attestation_dir: str) -> dict:
    envelope = create_envelope(
        command="os_grade_promote",
        principal="root-host-phase4",
        token_id=manifest["manifest_id"],
        lane="gondor",
        policy_id=bundle["policy_id"],
        policy_version=bundle["policy_version"],
        verdict="ALLOW",
        artifact_digest=_manifest_digest(manifest),
        policy_verdict="ALLOW",
        use_sigstore=should_use_sigstore(),
    )
    output_path = os.path.join(attestation_dir, DEFAULT_ENVELOPE_PATH_NAME)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(envelope, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return {
        "path": output_path,
        "signing_algorithm": envelope.get("signing_algorithm"),
        "signing_identity": envelope.get("signing_identity"),
        "transparency_receipt": envelope.get("transparency_receipt"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote Arda toward the OS-grade production milestone")
    parser.add_argument("--policy", default=str(REPO_ROOT / "arda_policy.json"))
    parser.add_argument("--bundle", default="/etc/arda/policy/active_bundle.json")
    parser.add_argument("--projection-plan", default="/etc/arda/policy/active_projection_plan.json")
    parser.add_argument("--manifest", default="/var/lib/arda/projection/measured-root.json")
    parser.add_argument("--attestation-dir", default=os.environ.get("ARDA_ATTESTATION_DIR", DEFAULT_ATTESTATION_DIR))
    parser.add_argument("--path", action="append", default=["/usr/bin/python3", "/usr/bin/sudo"])
    parser.add_argument("--generation", type=int)
    parser.add_argument("--seed-running-processes", action="store_true")
    parser.add_argument("--require-secure-boot", action="store_true")
    parser.add_argument("--require-tpm-capture", action="store_true")
    parser.add_argument("--capture-tpm", action="store_true")
    args = parser.parse_args()

    steps = []

    def step(name: str, script: str, command_args: list[str]) -> dict:
        rc, payload, raw = _run(script, command_args)
        record = {"step": name, "ok": rc == 0, "returncode": rc, "payload": payload, "raw": raw if rc != 0 else None}
        steps.append(record)
        if rc != 0:
            raise RuntimeError(name)
        return record

    try:
        os.makedirs(os.path.dirname(args.bundle), exist_ok=True)
        os.makedirs(os.path.dirname(args.projection_plan), exist_ok=True)
        os.makedirs(os.path.dirname(args.manifest), exist_ok=True)
        os.makedirs(args.attestation_dir, exist_ok=True)
        generation_db = os.environ.get("ARDA_MEASURED_GENERATION_DB", DEFAULT_GENERATION_DB)
        os.environ.setdefault("ARDA_MEASURED_GENERATION_DB", generation_db)

        step("compile_policy", "arda_compile_policy.py", ["--policy", args.policy, "--output", args.bundle, "--verify-after"])
        step(
            "compile_projection",
            "arda_compile_projection.py",
            [
                "--bundle",
                args.bundle,
                "--output",
                args.projection_plan,
                "--enforcement-mode",
                "legacy_inode",
                *sum([["--path", path] for path in args.path], []),
            ],
        )
        policy_generation = None
        with open(args.projection_plan, "r", encoding="utf-8") as handle:
            plan = json.load(handle)
            policy_generation = plan["targets"]["constitutional_state"]["policy_generation"]
        bundle = _read_json(args.bundle)
        attestation_binding = _attestation_binding(args.attestation_dir)

        node_id = os.uname().nodename
        generation = args.generation or _next_generation(node_id, generation_db)
        manifest_args = [
            "--policy-generation",
            policy_generation,
            "--generation",
            str(generation),
            "--node-id",
            node_id,
            "--output",
            args.manifest,
        ]
        if attestation_binding.get("attestation_result_id"):
            manifest_args.extend(["--attestation-result-id", attestation_binding["attestation_result_id"]])
        if attestation_binding.get("attestation_evidence_digest"):
            manifest_args.extend(["--attestation-evidence-digest", attestation_binding["attestation_evidence_digest"]])
        for path in args.path:
            manifest_args.extend(["--path", path])
        step("build_measured_manifest", "arda_build_measured_manifest.py", manifest_args)

        service = OsEnforcementService()
        try:
            if args.capture_tpm:
                capture = service.capture_phase4_live_attestation(args.attestation_dir)
                steps.append({"step": "capture_tpm_attestation", "ok": True, "returncode": 0, "payload": capture, "raw": None})

            project = service.project_pinned_policy(
                harmonic_paths=plan["targets"]["harmony_allow_paths"],
                enforcement_mode=plan["targets"]["enforcement_mode"],
                constitutional_state=plan["targets"]["constitutional_state"],
                seed_running_processes=args.seed_running_processes,
            )
            steps.append({"step": "project_policy_legacy_inode", "ok": True, "returncode": 0, "payload": project, "raw": None})

            manifest = _read_json(args.manifest)
            preflight = service.preflight_measured_manifest(manifest)
            steps.append({"step": "preflight_measured_manifest", "ok": preflight.get("ok") is True, "returncode": 0 if preflight.get("ok") else 1, "payload": {"preflight": preflight}, "raw": None if preflight.get("ok") else json.dumps(preflight, indent=2)})
            if not preflight.get("ok"):
                raise RuntimeError("preflight_measured_manifest")

            staged = service.stage_measured_manifest(manifest)
            steps.append({"step": "stage_measured_manifest", "ok": True, "returncode": 0, "payload": staged, "raw": None})
            manifest_id = manifest["manifest_id"]
            activated = service.activate_staged_measured_manifest(manifest_id)
            steps.append({"step": "activate_measured_manifest", "ok": True, "returncode": 0, "payload": activated, "raw": None})
            projected = service.project_staged_measured_manifest(manifest_id)
            steps.append({"step": "project_measured_manifest_fsverity", "ok": True, "returncode": 0, "payload": projected, "raw": None})
            envelope = _write_attestation_envelope(
                manifest=manifest,
                bundle=bundle,
                attestation_dir=args.attestation_dir,
            )
            steps.append({"step": "write_attestation_envelope", "ok": True, "returncode": 0, "payload": envelope, "raw": None})
            try:
                gate = build_gate_report(
                    service.get_status(),
                    require_secure_boot=args.require_secure_boot,
                    require_tpm_capture=args.require_tpm_capture,
                    attestation_dir=args.attestation_dir,
                )
            except Exception as error:
                gate = {
                    "ok": False,
                    "boundary": "kernel-authoritative substrate, gate probe failed",
                    "checks": {},
                    "blockers": ["os_grade_gate_probe_error"],
                    "error": str(error),
                }
            steps.append({"step": "os_grade_gate", "ok": gate["ok"], "returncode": 0 if gate["ok"] else 1, "payload": gate, "raw": None if gate["ok"] else json.dumps(gate, indent=2)})
            ok = gate["ok"]
        finally:
            service.shutdown()
    except Exception:
        ok = False

    print(json.dumps({"ok": ok, "steps": steps}, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
