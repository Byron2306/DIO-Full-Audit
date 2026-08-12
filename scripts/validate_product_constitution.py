from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_META = {
    "meta_evidence",
    "meta_assurance",
    "meta_authority",
    "meta_room",
}
EXPECTED_WORK_PATTERNS = [f"WP{i:02d}" for i in range(1, 13)]
EXPECTED_PROFILE_CLASSES = {
    "domain",
    "framework",
    "authority",
    "connector",
    "output",
    "commercial",
}
EXPECTED_MANIFEST_PROFILE_KEYS = {
    "domain",
    "framework",
    "authority",
    "connector_pack",
    "output",
    "commercial",
}
EXPECTED_MATURITY = [
    "discovered",
    "registered",
    "composed",
    "internal_proof",
    "pilot_ready",
    "customer_validated",
    "repeatable",
    "economically_proven",
    "scale_ready",
]
EXPECTED_OPERATIONAL_FLAGS = {
    "routable",
    "governable",
    "executable",
    "campaign_enabled",
    "externally_validated",
    "continuous_assurance_ready",
    "revenue_proven",
}
EXPECTED_SUITES = {
    "education_research",
    "evidence_assurance",
    "public_programme_ops",
    "ai_digital_trust",
    "enterprise_operations",
    "demand_presence",
}


class ConstitutionError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConstitutionError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConstitutionError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConstitutionError(f"expected JSON object in {path}")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConstitutionError(message)


def ids(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("id") or "") for item in items]


def validate(root: Path) -> list[str]:
    checks: list[str] = []

    portfolio = root / "config" / "portfolio"
    constitution_path = portfolio / "constitution.json"
    work_patterns_path = portfolio / "work_patterns.json"
    meta_path = portfolio / "meta_capabilities.json"
    profiles_path = portfolio / "profile_classes.json"
    maturity_path = portfolio / "maturity_vocabulary.json"
    suites_path = portfolio / "suites.json"
    boundaries_path = portfolio / "repo_boundaries.json"
    manifest_schema_path = root / "schemas" / "dio_product_manifest.schema.json"

    constitution = load_json(constitution_path)
    require(constitution.get("schema") == "dio.product_constitution.v1", "unexpected constitution schema")
    require(constitution.get("constitution_version") == "1.0.0", "unexpected constitution version")
    require(constitution.get("status") == "FROZEN", "product constitution must be FROZEN")
    laws = constitution.get("constitutional_laws") or {}
    require(laws.get("one_sovereign_organism") is True, "one-sovereign-organism law is not frozen true")
    require(laws.get("products_request_capabilities_not_organs") is True, "products must request capabilities, not organs")
    require(laws.get("profiles_are_configuration_not_runtime") is True, "profiles must remain configuration, not runtime")
    require(laws.get("missing_required_executor_state") == "REFUSE", "missing executor must resolve to REFUSE")
    require(laws.get("kernel_authority") == "Valinor", "Valinor must remain kernel authority")
    require(laws.get("execution_identity_authority") == "ARDA", "ARDA must remain execution identity authority")
    checks.append("constitution frozen")

    canonical_paths = constitution.get("canonical_paths") or {}
    required_path_keys = {
        "product_manifest_schema",
        "work_pattern_registry",
        "meta_capability_registry",
        "profile_class_registry",
        "maturity_vocabulary",
        "suite_registry",
        "repo_boundaries",
    }
    require(required_path_keys.issubset(canonical_paths), "constitution canonical_paths is incomplete")
    for key in sorted(required_path_keys):
        require((root / str(canonical_paths[key])).is_file(), f"canonical path missing for {key}: {canonical_paths[key]}")
    checks.append("canonical paths present")

    meta = load_json(meta_path)
    meta_items = meta.get("meta_capabilities") or []
    require(isinstance(meta_items, list), "meta_capabilities must be a list")
    meta_ids = set(ids(meta_items))
    require(meta_ids == EXPECTED_META, f"META registry drift: {sorted(meta_ids)}")
    require((meta.get("laws") or {}).get("exact_primitive_count") == 4, "META exact primitive count law must equal 4")
    checks.append("exactly four META primitives")

    work_patterns = load_json(work_patterns_path)
    pattern_items = work_patterns.get("work_patterns") or []
    require(isinstance(pattern_items, list), "work_patterns must be a list")
    pattern_ids = ids(pattern_items)
    require(pattern_ids == EXPECTED_WORK_PATTERNS, f"work-pattern registry drift: {pattern_ids}")
    require(all(str(item.get("human_boundary") or "").strip() for item in pattern_items), "every work pattern requires a human boundary")
    pattern_laws = work_patterns.get("laws") or {}
    require(pattern_laws.get("patterns_are_domain_independent") is True, "work patterns must remain domain-independent")
    require(pattern_laws.get("patterns_create_authority") is False, "work patterns may not create authority")
    require(pattern_laws.get("patterns_create_executors") is False, "work patterns may not create executors")
    require(pattern_laws.get("canonical_case_grammar_required") is True, "work patterns must use canonical case grammar")
    checks.append("exactly twelve work patterns")

    profiles = load_json(profiles_path)
    profile_items = profiles.get("profile_classes") or []
    profile_ids = set(ids(profile_items))
    require(profile_ids == EXPECTED_PROFILE_CLASSES, f"profile-class registry drift: {sorted(profile_ids)}")
    profile_laws = profiles.get("laws") or {}
    require(profile_laws.get("classes_are_closed_in_v1") is True, "profile classes must be closed in v1")
    require(profile_laws.get("profiles_create_authority") is False, "profiles may not create authority")
    require(profile_laws.get("profiles_create_executors") is False, "profiles may not create executors")
    require(profile_laws.get("profiles_are_declarative") is True, "profiles must be declarative")
    checks.append("exactly six profile classes")

    maturity = load_json(maturity_path)
    maturity_ids = ids(maturity.get("states") or [])
    require(maturity_ids == EXPECTED_MATURITY, f"maturity vocabulary drift: {maturity_ids}")
    ranks = [item.get("rank") for item in maturity.get("states") or []]
    require(ranks == list(range(9)), f"maturity ranks must be 0..8, got {ranks}")
    flag_ids = set(ids(maturity.get("operational_flags") or []))
    require(flag_ids == EXPECTED_OPERATIONAL_FLAGS, f"operational-flag drift: {sorted(flag_ids)}")
    maturity_laws = maturity.get("laws") or {}
    require(maturity_laws.get("architecture_never_implies_maturity") is True, "architecture must never imply maturity")
    require(maturity_laws.get("promotion_requires_evidence") is True, "maturity promotion must require evidence")
    require(maturity_laws.get("no_automatic_legacy_status_mapping") is True, "legacy status mapping must not auto-promote maturity")
    checks.append("nine-state maturity vocabulary + independent flags")

    suites = load_json(suites_path)
    suite_ids = set(ids(suites.get("suites") or []))
    require(suite_ids == EXPECTED_SUITES, f"suite registry drift: {sorted(suite_ids)}")
    suite_laws = suites.get("laws") or {}
    require(suite_laws.get("suite_is_market_packaging_only") is True, "suites must remain market packaging only")
    require(suite_laws.get("suite_changes_runtime") is False, "suite membership may not change runtime")
    require(suite_laws.get("suite_creates_authority") is False, "suite membership may not create authority")
    checks.append("six suites remain packaging-only")

    boundaries = load_json(boundaries_path)
    boundary_laws = boundaries.get("laws") or {}
    require(boundary_laws.get("manifest_contains_no_executor_implementation") is True, "manifest may not contain executor implementation")
    require(boundary_laws.get("profile_contains_no_executor_implementation") is True, "profiles may not contain executor implementation")
    require(boundary_laws.get("suite_contains_no_runtime_implementation") is True, "suites may not contain runtime implementation")
    require(boundary_laws.get("vertical_may_add_adapter_not_parallel_core_engine") is True, "verticals must prefer adapters over parallel core engines")
    checks.append("repository anti-fork boundaries frozen")

    manifest_schema = load_json(manifest_schema_path)
    require(manifest_schema.get("$id") == "dio.product_manifest.v1", "unexpected product manifest schema id")
    manifest_props = manifest_schema.get("properties") or {}
    forbidden_top_level = {"organs", "organ_wiring", "executor", "runner", "kernel_authority"}
    require(not forbidden_top_level.intersection(manifest_props), "manifest schema exposes forbidden direct runtime/organ wiring fields")

    pattern_enum = set((((manifest_props.get("work_patterns") or {}).get("items") or {}).get("enum") or []))
    require(pattern_enum == set(EXPECTED_WORK_PATTERNS), "manifest work-pattern enum disagrees with registry")
    meta_enum = set((((manifest_props.get("meta_capabilities") or {}).get("items") or {}).get("enum") or []))
    require(meta_enum == EXPECTED_META, "manifest META enum disagrees with registry")
    suite_enum = set((((manifest_props.get("suite_ids") or {}).get("items") or {}).get("enum") or []))
    require(suite_enum == EXPECTED_SUITES, "manifest suite enum disagrees with registry")

    manifest_profile_props = set((((manifest_props.get("profiles") or {}).get("properties") or {}).keys()))
    require(manifest_profile_props == EXPECTED_MANIFEST_PROFILE_KEYS, f"manifest profile classes drift: {sorted(manifest_profile_props)}")

    executor_policy = (manifest_props.get("executor_policy") or {}).get("properties") or {}
    require((executor_policy.get("resolution") or {}).get("const") == "compiler", "executor resolution must belong to compiler")
    require((executor_policy.get("missing_required_executor") or {}).get("const") == "REFUSE", "missing required executor must be REFUSE")

    maturity_props = (manifest_props.get("maturity") or {}).get("properties") or {}
    state_enum = set((maturity_props.get("state") or {}).get("enum") or [])
    require(state_enum == set(EXPECTED_MATURITY), "manifest maturity states disagree with vocabulary")
    operational_props = set((((maturity_props.get("operational_flags") or {}).get("properties") or {}).keys()))
    require(operational_props == EXPECTED_OPERATIONAL_FLAGS, "manifest operational flags disagree with vocabulary")
    checks.append("manifest schema agrees with constitutional registries")

    compatibility_paths = [
        root / "config" / "dio_product_portfolio.json",
        root / "schemas" / "dio_product_request.schema.json",
        root / "schemas" / "dio_governed_case.schema.json",
        root / "products" / "registry.py",
    ]
    for path in compatibility_paths:
        require(path.is_file(), f"current Product Platform compatibility artifact missing: {path}")
    checks.append("current Product Platform compatibility artifacts preserved")

    phase = constitution.get("phase_boundaries") or {}
    forbidden = set(phase.get("forbidden_in_phase_0") or [])
    require("bespoke ContractProof runtime" in forbidden, "Phase 0 must forbid bespoke ContractProof runtime")
    require("bespoke TenderProof runtime" in forbidden, "Phase 0 must forbid bespoke TenderProof runtime")
    require("bespoke GrantProof runtime" in forbidden, "Phase 0 must forbid bespoke GrantProof runtime")
    require("bespoke PermitProof runtime" in forbidden, "Phase 0 must forbid bespoke PermitProof runtime")
    require("new execution authority" in forbidden, "Phase 0 must forbid new execution authority")
    require("automatic maturity promotion" in forbidden, "Phase 0 must forbid automatic maturity promotion")
    checks.append("Phase 0 scope boundary frozen")

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the frozen DIO Product Constitution and Phase 0 registries.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    try:
        checks = validate(args.root.resolve())
    except ConstitutionError as exc:
        print(f"DIO_PRODUCT_CONSTITUTION_REFUSE: {exc}", file=sys.stderr)
        return 1

    for check in checks:
        print(f"ALLOW {check}")
    print("DIO_PRODUCT_CONSTITUTION_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
