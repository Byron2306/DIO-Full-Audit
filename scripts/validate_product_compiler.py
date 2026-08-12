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
        require(bool(validate_constitution(ROOT)), "Phase 0 constitution validation returned no checks")
        require(bool(validate_profiles(ROOT)), "Phase 1 profile validation returned no checks")
        manifest_path = ROOT / "config" / "products" / "manifests" / "contractproof.json"
        manifest = load_json(manifest_path)
        validate_manifest_schema(ROOT, manifest)

        compiled_a = compile_manifest(ROOT, manifest_path)
        compiled_b = compile_manifest(ROOT, manifest_path)
        validate_compiled_contract(compiled_a)
        require(compiled_a["composition_fingerprint"] == compiled_b["composition_fingerprint"], "composition fingerprint lost determinism")
        require(compiled_a["compilation_fingerprint"] == compiled_b["compilation_fingerprint"], "compilation fingerprint lost determinism")
        require(compiled_a["compiler_provenance"]["source_ref"] == "products/compiler.py", "compiler provenance source ref drift")
        require(str(compiled_a["compiler_provenance"]["source_sha256"]).startswith("sha256:"), "compiler source hash missing")
        require(compiled_a["product_id"] == "dio_contractproof", "unexpected reference product")
        require({item["id"] for item in compiled_a["work_patterns"]} == {"WP01", "WP05", "WP11"}, "ContractProof work-pattern composition drift")
        require({item["id"] for item in compiled_a["meta_capabilities"]} == {"meta_evidence", "meta_assurance", "meta_authority", "meta_room"}, "ContractProof META composition drift")
        require(len(compiled_a["profile_bindings"]) == 6, "ContractProof must bind all six profile classes")

        catalog, _ = load_capability_catalog(ROOT)
        capability_rows = {item["capability_id"]: item for item in compiled_a["capability_plan"]}
        for capability_id, catalog_row in catalog.items():
            if capability_id not in capability_rows:
                continue
            expected = "RESOLVED" if catalog_row["status"] == "available" and any(
                "*" in provider.get("product_scope", []) or "dio_contractproof" in provider.get("product_scope", [])
                for provider in catalog_row.get("providers") or []
            ) else "PLANNED" if catalog_row["status"] == "planned" else None
            if expected:
                require(capability_rows[capability_id]["resolution_state"] == expected, f"capability frontier mismatch for {capability_id}")

        capitalroom = next(row for row in catalog["proof.room.compile"]["providers"] if row["provider_id"] == "capitalroom_proof_room")
        require("dio_contractproof" not in capitalroom["product_scope"], "CapitalRoom provider scope was broadened to ContractProof")
        room = capability_rows["proof.room.compile"]
        if room["resolution_state"] == "RESOLVED":
            require(room["provider"]["provider_id"] != "capitalroom_proof_room", "ContractProof resolved through inapplicable CapitalRoom provider")

        require(compiled_a["gates"]["composition"]["state"] == "ALLOW", "valid composition should ALLOW")
        require(compiled_a["gates"]["planning"]["state"] in {"ALLOW", "NEEDS_IMPLEMENTATION"}, "unexpected planning gate")
        require(compiled_a["gates"]["execution"]["state"] in {"REFUSE", "NEEDS_YOU"}, "compiler created autonomous execution authority")
        require(compiled_a["gates"]["execution"]["state"] != "ALLOW", "compiler must never autonomously ALLOW execution")
        require(compiled_a["gates"]["human_review"]["state"] == "NEEDS_YOU", "human review gate drift")
        require(compiled_a["gates"]["external_release"]["state"] == "REFUSE", "internal-only ContractProof must refuse external release")

        manifest_with_organs = copy.deepcopy(manifest)
        manifest_with_organs["organs"] = ["Evidex"]
        expect_compiler_refusal(lambda: validate_manifest_schema(ROOT, manifest_with_organs), "Additional properties are not allowed")
        patterns, _ = load_work_patterns(ROOT)
        meta, _ = load_meta_capabilities(ROOT)
        incomplete_meta = copy.deepcopy(manifest)
        incomplete_meta["meta_capabilities"] = ["meta_evidence", "meta_assurance", "meta_room"]
        expect_compiler_refusal(lambda: validate_pattern_meta_composition(incomplete_meta, patterns, meta), "META composition incomplete")
        index = load_profile_index(ROOT)
        stale_profile = copy.deepcopy(manifest)
        stale_profile["profiles"]["framework"][0]["content_hash"] = "sha256:" + ("0" * 64)
        expect_compiler_refusal(lambda: bind_profiles(ROOT, stale_profile, index), "profile content hash mismatch")

        target = write_compilation(ROOT, compiled_a)
        required_artifacts = {
            "COMPILED_PRODUCT.json", "CASE_TEMPLATE.json", "CAPABILITY_PLAN.json", "GATE_PLAN.json",
            "OUTPUT_PLAN.json", "TEST_PLAN.json", "COMPILATION_RECEIPT.json",
        }
        observed = {path.name for path in target.glob("*.json")}
        require(required_artifacts.issubset(observed), "compiled artifact set incomplete")
        persisted = json.loads((target / "COMPILED_PRODUCT.json").read_text(encoding="utf-8"))
        receipt = json.loads((target / "COMPILATION_RECEIPT.json").read_text(encoding="utf-8"))
        require(persisted["composition_fingerprint"] == compiled_a["composition_fingerprint"], "persisted composition fingerprint drift")
        require(persisted["compilation_fingerprint"] == compiled_a["compilation_fingerprint"], "persisted compilation fingerprint drift")
        require(receipt["execution_gate"] == compiled_a["gates"]["execution"]["state"], "receipt execution gate drift")
        require(receipt["external_release_gate"] == "REFUSE", "receipt external-release refusal drift")

    except (AcceptanceError, CompilerError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DIO_PRODUCT_COMPILER_REFUSE: {exc}", file=sys.stderr)
        return 1

    print("ALLOW Phase 0 constitution remains valid")
    print("ALLOW Phase 1 profile bindings remain valid")
    print("ALLOW manifest schema rejects direct organ wiring")
    print("ALLOW work-pattern META dependencies are enforced")
    print("ALLOW profile version/hash bindings are enforced")
    print("ALLOW capability resolution is deterministic across an advancing earned frontier")
    print("ALLOW CapitalRoom remains product-scoped instead of becoming magically generic")
    print("ALLOW compiler never creates autonomous execution authority")
    print("ALLOW internal-only commercial policy produces external-release REFUSE")
    print("ALLOW composition and compilation fingerprints remain deterministic")
    print("ALLOW compiled artifacts and receipt preserve current governed gates")
    print("DIO_PRODUCT_COMPILER_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
