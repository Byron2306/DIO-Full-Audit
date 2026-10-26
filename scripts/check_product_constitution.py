from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PATTERNS = {f"WP{i:02d}" for i in range(1, 13)}
EXPECTED_META = {"meta_evidence", "meta_assurance", "meta_authority", "meta_room"}
EXPECTED_PROFILE_CLASSES = {"domain", "framework", "authority", "connector", "output", "commercial"}
EXPECTED_MATURITY = ["discovered", "registered", "composed", "internal_proof", "pilot_ready", "customer_validated", "repeatable", "economically_proven", "scale_ready"]
EXPECTED_FLAGS = {"routable", "governable", "executable", "campaign_enabled", "externally_validated", "continuous_assurance_ready", "revenue_proven"}
EXPECTED_SUITES = {"education_research", "evidence_assurance", "public_programme_ops", "ai_digital_trust", "enterprise_operations", "demand_presence"}

class ConstitutionError(RuntimeError):
    pass

def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def _ids(rows: list[dict], key: str = "id") -> list[str]:
    return [row[key] for row in rows]

def validate_constitution() -> dict:
    constitution = load_json("config/portfolio/constitution.json")
    patterns = load_json("config/portfolio/work_patterns.json")
    meta = load_json("config/portfolio/meta_capabilities.json")
    profiles = load_json("config/portfolio/profile_classes.json")
    maturity = load_json("config/portfolio/maturity_vocabulary.json")
    suites = load_json("config/portfolio/suites.json")
    boundaries = load_json("config/portfolio/repo_boundaries.json")
    manifest_schema = load_json("schemas/dio_product_manifest.schema.json")

    if constitution["status"] != "FROZEN": raise ConstitutionError("constitution_not_frozen")
    required_nouns = {"product", "profile", "organ", "executor", "suite", "incarnation"}
    if not required_nouns.issubset(constitution["canonical_definitions"]): raise ConstitutionError("canonical_nouns_incomplete")
    if constitution["constitutional_laws"]["missing_required_executor_state"] != "REFUSE": raise ConstitutionError("missing_executor_not_refuse")

    pattern_ids = _ids(patterns["work_patterns"])
    if set(pattern_ids) != EXPECTED_PATTERNS or len(pattern_ids) != 12: raise ConstitutionError("work_pattern_registry_not_exact")
    if len(pattern_ids) != len(set(pattern_ids)): raise ConstitutionError("duplicate_work_pattern")
    meta_ids = _ids(meta["meta_capabilities"])
    if set(meta_ids) != EXPECTED_META or len(meta_ids) != 4: raise ConstitutionError("meta_registry_not_exact")
    if len(meta_ids) != len(set(meta_ids)): raise ConstitutionError("duplicate_meta_capability")
    for pattern in patterns["work_patterns"]:
        if not set(pattern["primary_meta"]).issubset(EXPECTED_META): raise ConstitutionError(f"unknown_meta_in_{pattern['id']}")
        if not pattern["human_boundary"].strip(): raise ConstitutionError(f"missing_human_boundary_{pattern['id']}")

    if set(_ids(profiles["profile_classes"])) != EXPECTED_PROFILE_CLASSES: raise ConstitutionError("profile_classes_not_exact")
    maturity_ids = _ids(maturity["states"])
    if maturity_ids != EXPECTED_MATURITY: raise ConstitutionError("maturity_order_changed")
    if [row["rank"] for row in maturity["states"]] != list(range(9)): raise ConstitutionError("maturity_rank_changed")
    if set(_ids(maturity["operational_flags"])) != EXPECTED_FLAGS: raise ConstitutionError("operational_flags_changed")
    if set(_ids(suites["suites"])) != EXPECTED_SUITES: raise ConstitutionError("suite_registry_not_exact")
    if not suites["laws"]["suite_is_market_packaging_only"]: raise ConstitutionError("suite_runtime_semantics_detected")

    canonical_target = boundaries["migration"]["canonical_target"]
    if canonical_target != "config/products/manifests/": raise ConstitutionError("manifest_authority_path_changed")
    if meta["composition_authority"] != canonical_target: raise ConstitutionError("meta_registry_claims_composition_authority")

    Draft202012Validator.check_schema(manifest_schema)
    if manifest_schema["properties"]["executor_policy"]["properties"]["missing_required_executor"]["const"] != "REFUSE": raise ConstitutionError("manifest_can_bypass_missing_executor_refusal")
    manifest_text = json.dumps(manifest_schema, sort_keys=True)
    if any(term in manifest_text for term in ['"organ_plan"', '"organ_id"', '"executor_id"']): raise ConstitutionError("manifest_schema_hard_codes_runtime_wiring")

    manifests_dir = ROOT / "config" / "products" / "manifests"
    validator = Draft202012Validator(manifest_schema)
    manifest_count = 0
    for path in sorted(manifests_dir.glob("*.json")):
        validator.validate(json.loads(path.read_text(encoding="utf-8")))
        manifest_count += 1

    return {"state":"DIO_PRODUCT_CONSTITUTION_FROZEN","constitution_version":constitution["constitution_version"],"work_patterns":len(pattern_ids),"meta_capabilities":len(meta_ids),"profile_classes":len(EXPECTED_PROFILE_CLASSES),"maturity_states":len(maturity_ids),"operational_flags":len(EXPECTED_FLAGS),"suites":len(EXPECTED_SUITES),"product_manifests_validated":manifest_count,"composition_authority":canonical_target,"missing_required_executor":"REFUSE"}

def main() -> int:
    print(json.dumps(validate_constitution(), indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
