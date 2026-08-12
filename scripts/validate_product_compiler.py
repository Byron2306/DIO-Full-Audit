from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from products.compiler import (
    CompilerError,
    bind_profiles,
    compile_manifest,
    load_capability_catalog,
    load_json,
    load_meta_capabilities,
    load_profile_index,
    load_work_patterns,
    validate_manifest_schema,
    validate_pattern_meta_composition,
    write_compilation,
)
from validate_product_constitution import validate as validate_constitution
from validate_profiles import validate as validate_profiles


class AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def expect_compiler_refusal(fn, contains: str) -> None:
    try:
        fn()
    except CompilerError as exc:
        require(contains in str(exc), f"refusal mismatch; expected {contains!r}, got {exc!r}")
        return
    raise AcceptanceError(f"expected compiler refusal containing: {contains}")


def validate_compiled_contract(compiled: dict) -> None:
    schema = load_json(ROOT / "schemas" / "dio_compiled_product.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(compiled), key=lambda err: list(err.absolute_path))
    if errors:
        rendered = []
        for error in errors[:12]:
            where = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{where}: {error.message}")
        raise AcceptanceError("compiled product schema validation failed: " + " | ".join(rendered))


def main() -> int:
    try:
        constitution_checks = validate_constitution(ROOT)
        require(constitution_checks, "Phase 0 constitution validation returned no checks")
        profile_checks = validate_profiles(ROOT)
        require(profile_checks, "Phase 1 profile validation returned no checks")

        manifest_path = ROOT / "config" / "products" / "manifests" / "contractproof.json"
        manifest = load_json(manifest_path)
        validate_manifest_schema(ROOT, manifest)

        compiled_a = compile_manifest(ROOT, manifest_path)
        compiled_b = compile_manifest(ROOT, manifest_path)
        validate_compiled_contract(compiled_a)

        require(compiled_a["composition_fingerprint"] == compiled_b["composition_fingerprint"], "same inputs must produce identical composition fingerprints")
        require(compiled_a["product_id"] == "dio_contractproof", "unexpected reference product")
        require({item["id"] for item in compiled_a["work_patterns"]} == {"WP01", "WP05", "WP11"}, "ContractProof work-pattern composition drift")
        require({item["id"] for item in compiled_a["meta_capabilities"]} == {"meta_evidence", "meta_assurance", "meta_authority", "meta_room"}, "ContractProof META composition drift")
        require(len(compiled_a["profile_bindings"]) == 6, "ContractProof must bind one reference profile from each Phase 1 class")

        capability_rows = {item["capability_id"]: item for item in compiled_a["capability_plan"]}
        for capability_id in ("case.materialize", "evidence.provenance", "evidence.link", "proof.room.compile"):
            require(capability_rows[capability_id]["resolution_state"] == "RESOLVED", f"earned capability failed to resolve: {capability_id}")
        for capability_id in ("obligation.extract", "obligation.normalize", "obligation.deadlines", "obligation.evaluate"):
            require(capability_rows[capability_id]["resolution_state"] == "PLANNED", f"future Obligation capability must remain PLANNED in Phase 2: {capability_id}")
        require(capability_rows["product.executor.contractproof"]["resolution_state"] == "PLANNED", "ContractProof executor must remain unearned")

        require(compiled_a["gates"]["composition"]["state"] == "ALLOW", "valid composition should ALLOW")
        require(compiled_a["gates"]["planning"]["state"] == "NEEDS_IMPLEMENTATION", "unearned Obligation runtime should be explicit")
        require(compiled_a["gates"]["execution"]["state"] == "REFUSE", "compiler must refuse execution without earned executor")
        require(compiled_a["gates"]["human_review"]["state"] == "NEEDS_YOU", "human review gate must remain explicit")
        require(compiled_a["gates"]["external_release"]["state"] == "REFUSE", "internal-only reference product must refuse external release")

        manifest_with_organs = copy.deepcopy(manifest)
        manifest_with_organs["organs"] = ["Evidex"]
        expect_compiler_refusal(lambda: validate_manifest_schema(ROOT, manifest_with_organs), "Additional properties are not allowed")

        patterns, _ = load_work_patterns(ROOT)
        meta, _ = load_meta_capabilities(ROOT)
        incomplete_meta = copy.deepcopy(manifest)
        incomplete_meta["meta_capabilities"] = ["meta_evidence", "meta_assurance", "meta_room"]
        expect_compiler_refusal(
            lambda: validate_pattern_meta_composition(incomplete_meta, patterns, meta),
            "META composition incomplete",
        )

        index = load_profile_index(ROOT)
        stale_profile = copy.deepcopy(manifest)
        stale_profile["profiles"]["framework"][0]["content_hash"] = "sha256:" + ("0" * 64)
        expect_compiler_refusal(
            lambda: bind_profiles(ROOT, stale_profile, index),
            "profile content hash mismatch",
        )

        capability_catalog, _ = load_capability_catalog(ROOT)
        require(capability_catalog["product.executor.contractproof"]["status"] == "planned", "Phase 2 must not smuggle in a ContractProof executor")

        target = write_compilation(ROOT, compiled_a)
        required_artifacts = {
            "COMPILED_PRODUCT.json",
            "CASE_TEMPLATE.json",
            "CAPABILITY_PLAN.json",
            "GATE_PLAN.json",
            "OUTPUT_PLAN.json",
            "TEST_PLAN.json",
            "COMPILATION_RECEIPT.json",
        }
        observed_artifacts = {path.name for path in target.glob("*.json")}
        require(required_artifacts.issubset(observed_artifacts), f"compiled artifact set incomplete: {sorted(required_artifacts.difference(observed_artifacts))}")

        persisted = json.loads((target / "COMPILED_PRODUCT.json").read_text(encoding="utf-8"))
        receipt = json.loads((target / "COMPILATION_RECEIPT.json").read_text(encoding="utf-8"))
        require(persisted["composition_fingerprint"] == compiled_a["composition_fingerprint"], "persisted compiled product fingerprint drift")
        require(receipt["composition_fingerprint"] == compiled_a["composition_fingerprint"], "compilation receipt fingerprint drift")
        require(receipt["execution_gate"] == "REFUSE", "receipt must preserve execution refusal")
        require(receipt["external_release_gate"] == "REFUSE", "receipt must preserve external-release refusal")

    except (AcceptanceError, CompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DIO_PRODUCT_COMPILER_REFUSE: {exc}", file=sys.stderr)
        return 1

    print("ALLOW Phase 0 constitution remains valid")
    print("ALLOW Phase 1 profile bindings remain valid")
    print("ALLOW manifest schema rejects direct organ wiring")
    print("ALLOW work-pattern META dependencies are enforced")
    print("ALLOW profile version/hash bindings are enforced")
    print("ALLOW capability resolution is deterministic")
    print("ALLOW unearned capabilities remain visible instead of inferred")
    print("ALLOW missing ContractProof executor produces execution REFUSE")
    print("ALLOW internal-only commercial policy produces external-release REFUSE")
    print("ALLOW compiled artifacts and receipt preserve the composition fingerprint")
    print("DIO_PRODUCT_COMPILER_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
