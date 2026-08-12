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
        require(bool(validate_constitution(ROOT)), "Phase 0 constitution validation returned no checks")
        print("ALLOW Phase 0 constitution remains valid")
        require(bool(validate_profiles(ROOT)), "Phase 1 profile validation returned no checks")
        print("ALLOW Phase 1 profile foundation remains valid")

        manifest = ROOT / "config" / "products" / "manifests" / "contractproof.json"
        compiled_a = compile_manifest(ROOT, manifest)
        compiled_b = compile_manifest(ROOT, manifest)
        require(compiled_a["composition_fingerprint"] == compiled_b["composition_fingerprint"], "Phase 2 composition lost determinism")
        require(compiled_a["compilation_fingerprint"] == compiled_b["compilation_fingerprint"], "Phase 2 compilation lost determinism")
        require(compiled_a["gates"]["execution"]["state"] in {"REFUSE", "NEEDS_YOU"}, "compiler created autonomous execution authority")
        require(compiled_a["gates"]["execution"]["state"] != "ALLOW", "compiler execution may not be autonomous")
        require(compiled_a["gates"]["external_release"]["state"] == "REFUSE", "internal ContractProof external release drift")
        print("ALLOW Phase 2 compiler remains deterministic and human-gated")

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
        require(plan_a["execution_gate"]["state"] == "REFUSE", "work-pattern planner itself must remain non-executing")
        require(plan_a["compiler_execution_gate"]["state"] in {"REFUSE", "NEEDS_YOU"}, "runtime observed autonomous compiler execution")
        print("ALLOW deterministic runtime planning preserves authority and execution boundaries")

        catalog, _ = load_capability_catalog(ROOT)
        patterns = {row["work_pattern_id"]: row for row in plan_a["patterns"]}
        for pattern_id in ("WP01", "WP05", "WP11"):
            operations = patterns[pattern_id]["operations"]
            states = [row["resolution_state"] for row in operations]
            if all(state == "RESOLVED" for state in states):
                expected = "READY"
            elif any(state in {"UNAVAILABLE", "UNKNOWN"} for state in states):
                expected = "BLOCKED"
            elif all(state == "PLANNED" for state in states):
                expected = "PLANNED"
            else:
                expected = "PARTIAL"
            require(patterns[pattern_id]["runtime_state"] == expected, f"runtime state does not reflect current frontier for {pattern_id}")
        print("ALLOW Evidence, Obligation and Proof patterns track the current earned frontier")

        room_providers = catalog["proof.room.compile"]["providers"]
        capitalroom = next(row for row in room_providers if row["provider_id"] == "capitalroom_proof_room")
        require("dio_contractproof" not in capitalroom["product_scope"], "CapitalRoom scope was broadened to ContractProof")
        proof_ops = {row["operation_id"]: row for row in patterns["WP11"]["operations"]}
        if proof_ops["compile_portable_room"]["resolution_state"] == "RESOLVED":
            require(proof_ops["compile_portable_room"]["provider"]["provider_id"] != "capitalroom_proof_room", "ContractProof inherited inapplicable CapitalRoom provider")
        print("ALLOW proof provider applicability remains product-scoped instead of magically generic")

        unrelated_planned = {
            "intake.normalize", "intake.classify", "intake.missing_information",
            "document.project", "document.qa", "document.release.prepare",
        }
        for capability_id in unrelated_planned:
            require(catalog[capability_id]["status"] == "planned", f"unrelated Phase 3 frontier capability falsely earned: {capability_id}")
            require(catalog[capability_id]["providers"] == [], f"planned capability unexpectedly has provider: {capability_id}")
        print("ALLOW unrelated capability frontier remains planned until earned")

        for pattern in plan_a["patterns"]:
            require(pattern["human_gate"]["state"] == "NEEDS_YOU", f"human boundary lost for {pattern['work_pattern_id']}")
        print("ALLOW human boundaries remain explicit NEEDS_YOU gates")
        print("DIO_WORK_PATTERN_RUNTIME_READY")
        return 0
    except Exception as exc:
        print(f"DIO_WORK_PATTERN_RUNTIME_REFUSE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
