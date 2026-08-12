from __future__ import annotations

import copy
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from products.compiler import compile_manifest, load_capability_catalog, load_json
from products.work_pattern_runtime import FOCUS_PATTERNS, load_runtime_registry, plan_manifest
from validate_product_constitution import validate as validate_constitution
from validate_profiles import validate as validate_profiles


class AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def main() -> int:
    try:
        constitution_checks = validate_constitution(ROOT)
        require(bool(constitution_checks), "Phase 0 constitution validation returned no checks")
        print("ALLOW Phase 0 constitution remains valid")

        profile_checks = validate_profiles(ROOT)
        require(bool(profile_checks), "Phase 1 profile validation returned no checks")
        print("ALLOW Phase 1 profile foundation remains valid")

        manifest = ROOT / "config" / "products" / "manifests" / "contractproof.json"
        compiled_a = compile_manifest(ROOT, manifest)
        compiled_b = compile_manifest(ROOT, manifest)
        require(compiled_a["composition_fingerprint"] == compiled_b["composition_fingerprint"], "Phase 2 composition lost determinism")
        require(compiled_a["compilation_fingerprint"] == compiled_b["compilation_fingerprint"], "Phase 2 compilation lost determinism")
        require(compiled_a["gates"]["execution"]["state"] == "REFUSE", "ContractProof execution refusal was relaxed")
        print("ALLOW Phase 2 compiler remains deterministic and fail-closed")

        contracts, registry, _ = load_runtime_registry(ROOT)
        require(set(contracts) == {f"WP{index:02d}" for index in range(1, 13)}, "runtime registry must declare exactly twelve patterns")
        require(set(registry["focus_patterns"]) == FOCUS_PATTERNS, "Phase 3 focus set drift")
        print("ALLOW twelve canonical contracts registered with five Phase 3 focus patterns")

        for pattern_id, contract in contracts.items():
            for operation in contract["operations"]:
                require(operation["execution_required"] is False, f"execution operation leaked into {pattern_id}")
                require(not operation["capability_id"].startswith("product.executor."), f"executor binding leaked into {pattern_id}")
        print("ALLOW work-pattern contracts remain capability-only and non-executing")

        schema = load_json(ROOT / "schemas" / "dio_work_pattern_runtime.schema.json")
        tampered = copy.deepcopy(registry)
        tampered["contracts"][0]["operations"][0]["provider"] = "Evidex"
        errors = list(Draft202012Validator(schema).iter_errors(tampered))
        require(any("Additional properties are not allowed" in error.message for error in errors), "runtime schema failed to reject direct provider wiring")
        print("ALLOW direct provider/organ wiring is schema-refused")

        plan_a = plan_manifest(ROOT, manifest)
        plan_b = plan_manifest(ROOT, manifest)
        require(plan_a["runtime_fingerprint"] == plan_b["runtime_fingerprint"], "runtime plan fingerprint is not deterministic")
        require(plan_a["authority_created"] is False and plan_a["executor_created"] is False, "runtime created authority or executor")
        require(plan_a["execution_gate"]["state"] == "REFUSE", "Phase 3 runtime execution gate must REFUSE")
        require(plan_a["compiler_execution_gate"]["state"] == "REFUSE", "Phase 3 runtime relaxed compiler execution refusal")
        print("ALLOW deterministic runtime planning preserves authority and execution boundaries")

        patterns = {row["work_pattern_id"]: row for row in plan_a["patterns"]}
        require(patterns["WP01"]["runtime_state"] == "PARTIAL", "ContractProof Evidence pattern must remain PARTIAL until evidence frontier advances")
        require(patterns["WP11"]["runtime_state"] == "BLOCKED", "ContractProof Proof pattern must remain BLOCKED by provider applicability")

        catalog, _ = load_capability_catalog(ROOT)
        obligation_ops = {row["operation_id"]: row for row in patterns["WP05"]["operations"]}
        obligation_capabilities = {
            "extract_obligations": "obligation.extract",
            "normalize_obligations": "obligation.normalize",
            "identify_deadlines": "obligation.deadlines",
            "assess_status": "obligation.evaluate",
        }
        all_earned = True
        for operation_id, capability_id in obligation_capabilities.items():
            expected = "RESOLVED" if catalog[capability_id]["status"] == "available" else "PLANNED"
            require(obligation_ops[operation_id]["resolution_state"] == expected, f"work-pattern frontier drift for {operation_id}")
            all_earned = all_earned and expected == "RESOLVED"
        require(obligation_ops["bind_evidence"]["resolution_state"] == "RESOLVED", "earned generic evidence linking should remain reusable")
        expected_wp05 = "READY" if all_earned else "PARTIAL"
        require(patterns["WP05"]["runtime_state"] == expected_wp05, "Obligation work-pattern runtime state does not reflect capability truth")
        print("ALLOW Obligation work pattern tracks the current earned capability frontier")

        proof_ops = {row["operation_id"]: row for row in patterns["WP11"]["operations"]}
        require(proof_ops["compile_portable_room"]["resolution_state"] == "UNAVAILABLE", "ContractProof must not inherit CapitalRoom proof provider")
        require("no earned provider declares applicability" in proof_ops["compile_portable_room"]["reason"], "proof provider refusal reason drift")
        print("ALLOW existing proof provider remains product-scoped instead of magically generic")

        new_planned = {
            "evidence.sufficiency",
            "evidence.gaps",
            "intake.normalize",
            "intake.classify",
            "intake.missing_information",
            "document.project",
            "document.qa",
            "document.release.prepare",
            "proof.integrity.verify",
            "proof.disclosure.prepare",
        }
        for capability_id in new_planned:
            require(catalog[capability_id]["status"] == "planned", f"unearned Phase 3 frontier capability falsely marked earned: {capability_id}")
            require(catalog[capability_id]["providers"] == [], f"planned Phase 3 capability unexpectedly has a provider: {capability_id}")
        print("ALLOW remaining Phase 3 capability frontier stays planned until earned")

        for pattern in plan_a["patterns"]:
            require(pattern["human_gate"]["state"] == "NEEDS_YOU", f"human boundary lost for {pattern['work_pattern_id']}")
        print("ALLOW human boundaries remain explicit NEEDS_YOU gates")

        print("DIO_WORK_PATTERN_RUNTIME_READY")
        return 0
    except (AcceptanceError, Exception) as exc:
        print(f"DIO_WORK_PATTERN_RUNTIME_REFUSE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
