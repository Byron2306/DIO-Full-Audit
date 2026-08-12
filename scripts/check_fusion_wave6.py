#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CORE_ROOT = HERE.parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from composition.orchestrator import load_composition_profiles
from executors.vertical import load_vertical_executor_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIO Fusion Wave 6 Cross-Organ Composition readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    blockers: list[dict[str, str]] = []

    wave5_path = workspace / "receipts" / "fusion-wave5-latest.json"
    try:
        wave5 = json.loads(wave5_path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append({"code": "FUSION_WAVE5_RECEIPT_INVALID", "message": str(exc)})
        wave5 = {}
    if wave5.get("state") != "FUSION_WAVE5_READY":
        blockers.append({
            "code": "FUSION_WAVE5_NOT_READY",
            "message": f"Expected FUSION_WAVE5_READY, got {wave5.get('state')!r}.",
        })

    required_files = [
        core / "composition" / "orchestrator.py",
        core / "composition" / "case_bridge.py",
        core / "config" / "dio_composition_profiles.json",
        core / "schemas" / "dio_composition_profiles.schema.json",
        core / "tests" / "test_cross_organ_composition.py",
    ]
    for path in required_files:
        if not path.is_file():
            blockers.append({"code": "COMPOSITION_FILE_MISSING", "message": str(path)})

    try:
        registry = load_composition_profiles(core / "config" / "dio_composition_profiles.json")
    except Exception as exc:
        blockers.append({"code": "COMPOSITION_REGISTRY_INVALID", "message": f"{type(exc).__name__}: {exc}"})
        registry = {"profiles": [], "laws": {}}

    profiles = {row.get("profile_id"): row for row in registry.get("profiles") or []}
    full = profiles.get("full_governed_external_action") or {}
    internal = profiles.get("governed_internal_artifact") or {}
    if not full:
        blockers.append({"code": "FULL_COMPOSITION_PROFILE_MISSING", "message": "full_governed_external_action"})
    if not internal:
        blockers.append({"code": "INTERNAL_COMPOSITION_PROFILE_MISSING", "message": "governed_internal_artifact"})

    expected_full_stages = {
        "ingress",
        "epistemic",
        "provenance",
        "custody",
        "adversarial",
        "coherence",
        "framework",
        "legal_readiness",
        "human_authority",
        "capability_lease",
        "kernel_authority",
        "execution_identity",
        "vertical_execution",
        "egress",
    }
    observed_full_stages = {row.get("stage_id") for row in full.get("stages") or []}
    if observed_full_stages != expected_full_stages:
        blockers.append({
            "code": "FULL_COMPOSITION_TOPOLOGY_DRIFT",
            "message": "missing=" + ",".join(sorted(expected_full_stages - observed_full_stages)) + ";extra=" + ",".join(sorted(observed_full_stages - expected_full_stages)),
        })

    full_stages = {row.get("stage_id"): row for row in full.get("stages") or []}
    if set((full_stages.get("vertical_execution") or {}).get("depends_on") or []) != {"kernel_authority", "execution_identity"}:
        blockers.append({"code": "EXECUTION_FANIN_DRIFT", "message": "Vertical execution must require both Valinor and ARDA branches."})
    if set((full_stages.get("custody") or {}).get("depends_on") or []) != {"epistemic", "provenance"}:
        blockers.append({"code": "EVIDENCE_FANIN_DRIFT", "message": "BEAST custody must bind Sophia and Evidex branches."})
    if (full_stages.get("kernel_authority") or {}).get("system_id") != "valinor":
        blockers.append({"code": "KERNEL_AUTHORITY_DRIFT", "message": "Valinor is not the sole kernel-authority composition stage."})
    if (full_stages.get("execution_identity") or {}).get("system_id") != "arda":
        blockers.append({"code": "ARDA_ROLE_DRIFT", "message": "ARDA is not the execution-identity composition stage."})

    laws = registry.get("laws") or {}
    required_laws = {
        "composition_has_no_authority",
        "same_case_required",
        "dependency_receipts_hash_bound",
        "required_stages_cannot_be_skipped",
        "machine_evidence_is_not_human_authority",
        "valinor_remains_sole_kernel_authority",
        "arda_remains_execution_identity_only",
        "external_execution_requires_wave5_bundle",
    }
    disabled = sorted(name for name in required_laws if laws.get(name) is not True)
    if disabled:
        blockers.append({"code": "COMPOSITION_LAW_DISABLED", "message": ",".join(disabled)})

    try:
        executors = load_vertical_executor_registry(core / "config" / "dio_vertical_executors.json")
        external_bound = [
            (executor.get("executor_id"), cap.get("capability"))
            for executor in executors.get("executors") or []
            for cap in executor.get("capabilities") or []
            if cap.get("binding_state") == "bound" and cap.get("external_side_effect") is True
        ]
    except Exception as exc:
        blockers.append({"code": "WAVE5_EXECUTOR_REGISTRY_INVALID", "message": f"{type(exc).__name__}: {exc}"})
        external_bound = []
    if not external_bound:
        blockers.append({"code": "NO_EXTERNAL_BOUND_EXECUTOR", "message": "Full external composition has no truthfully bound Wave 5 external executor."})

    full_systems = {
        row.get("system_id")
        for row in full.get("stages") or []
        if row.get("system_id") not in {"human_or_organisation", "bounded_vertical_executor"}
    }
    state = "FUSION_WAVE6_READY" if not blockers else "BLOCKED"
    receipt = {
        "schema": "dio.fusion.wave6.receipt.v1",
        "state": state,
        "depends_on": {
            "fusion_wave5_state": wave5.get("state"),
            "fusion_wave5_receipt": str(wave5_path),
        },
        "profiles": len(registry.get("profiles") or []),
        "full_profile_stages": len(full.get("stages") or []),
        "cross_organ_systems": len(full_systems),
        "external_bound_executor_options": len(external_bound),
        "composition_authority": False,
        "kernel_authority": "Valinor",
        "execution_identity_authority": "ARDA",
        "laws": {name: True for name in sorted(required_laws)},
        "blockers": blockers,
        "receipt": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if state == "FUSION_WAVE6_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
