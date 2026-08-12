from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROFILE_CLASS_DIRS = {
    "domains": "domain",
    "frameworks": "framework",
    "authorities": "authority",
    "connectors": "connector",
    "outputs": "output",
    "commercial": "commercial",
}

EXPECTED_REFERENCE_PROFILES = {
    "domain.project_delivery",
    "framework.contract_generic",
    "authority.contract_owner",
    "connector.files_readonly",
    "output.evidence_pack",
    "commercial.internal_proof",
}

FORBIDDEN_PROFILE_KEYS = {
    "executor",
    "runner",
    "kernel_authority",
    "execution_identity_authority",
    "maturity",
    "campaign_enabled",
    "revenue_proven",
    "customer_validated",
    "scale_ready",
}

REQUIRED_TOP_LEVEL = {
    "schema",
    "profile_version",
    "profile_id",
    "profile_class",
    "name",
    "status",
    "binding",
    "risk_boundary",
    "spec",
}

CLASS_REQUIRED_SPEC_KEYS = {
    "domain": {"object_types", "vocabulary", "human_boundaries", "forbidden_claims"},
    "framework": {"requirement_types", "state_vocabulary", "deadline_semantics", "human_boundaries", "forbidden_claims"},
    "authority": {"human_roles", "decision_boundaries", "capability_constraints", "forbidden_claims"},
    "connector": {"read_capabilities", "write_capabilities", "side_effects", "authority_requirements"},
    "output": {"artifact_types", "required_sections", "disclosure_rules", "qa_requirements"},
    "commercial": {"offer_state", "permitted_actions", "prohibited_actions", "claim_ceiling"},
}


class ProfileError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"invalid JSON in {path}: {exc}") from exc
    require(isinstance(payload, dict), f"expected JSON object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            found.add(str(key))
            found.update(walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(walk_keys(child))
    return found


def validate_source_binding(root: Path, profile_id: str, binding: dict[str, Any]) -> None:
    require(binding.get("state") == "BOUND", f"{profile_id}: binding.state must be BOUND")
    sources = binding.get("source_bindings")
    require(isinstance(sources, list) and sources, f"{profile_id}: at least one source binding is required")

    for source in sources:
        require(isinstance(source, dict), f"{profile_id}: source binding must be an object")
        source_ref = str(source.get("source_ref") or "")
        version = str(source.get("source_version") or "")
        content_hash = str(source.get("content_hash") or "")
        source_kind = str(source.get("source_kind") or "")
        authority_level = str(source.get("authority_level") or "")
        require(source_ref, f"{profile_id}: source_ref required")
        require(version, f"{profile_id}: source_version required")
        require(content_hash.startswith("sha256:") and len(content_hash) == 71, f"{profile_id}: invalid source content_hash")
        require(source_kind in {"internal_design", "policy", "contract", "standard", "regulation", "official_guidance", "customer_authority", "technical_specification"}, f"{profile_id}: unsupported source_kind {source_kind}")
        require(authority_level in {"internal_reference", "customer_authoritative", "externally_authoritative"}, f"{profile_id}: unsupported authority_level {authority_level}")

        source_path = (root / source_ref).resolve()
        require(source_path.is_relative_to(root.resolve()), f"{profile_id}: source_ref escapes repository root")
        require(source_path.is_file(), f"{profile_id}: bound source missing: {source_ref}")
        observed_hash = sha256_file(source_path)
        expected_hash = content_hash.split(":", 1)[1]
        require(observed_hash == expected_hash, f"{profile_id}: source hash mismatch for {source_ref}")


def validate_profile(root: Path, path: Path, expected_class: str) -> str:
    profile = load_json(path)
    missing = REQUIRED_TOP_LEVEL.difference(profile)
    require(not missing, f"{path}: missing required fields {sorted(missing)}")
    require(profile.get("schema") == "dio.profile.v1", f"{path}: unexpected schema")
    profile_id = str(profile.get("profile_id") or "")
    profile_class = str(profile.get("profile_class") or "")
    require(profile_class == expected_class, f"{profile_id}: class {profile_class} disagrees with directory class {expected_class}")
    require(profile_id.startswith(expected_class + "."), f"{profile_id}: profile_id prefix disagrees with class")
    require(profile.get("status") in {"internal_reference", "source_bound", "externally_validated", "deprecated"}, f"{profile_id}: invalid status")
    require(isinstance(profile.get("risk_boundary"), str) and len(profile["risk_boundary"].strip()) >= 8, f"{profile_id}: explicit risk_boundary required")

    forbidden = FORBIDDEN_PROFILE_KEYS.intersection(walk_keys(profile))
    require(not forbidden, f"{profile_id}: profile contains forbidden runtime/maturity keys {sorted(forbidden)}")

    spec = profile.get("spec")
    require(isinstance(spec, dict), f"{profile_id}: spec must be an object")
    required_spec = CLASS_REQUIRED_SPEC_KEYS[profile_class]
    require(required_spec.issubset(spec), f"{profile_id}: spec missing {sorted(required_spec.difference(spec))}")

    binding = profile.get("binding")
    require(isinstance(binding, dict), f"{profile_id}: binding must be an object")
    validate_source_binding(root, profile_id, binding)

    if profile.get("status") == "externally_validated":
        sources = binding.get("source_bindings") or []
        require(any(item.get("authority_level") == "externally_authoritative" for item in sources), f"{profile_id}: externally_validated requires an externally_authoritative source")

    if profile_class == "commercial" and spec.get("offer_state") == "internal_only":
        prohibited = set(spec.get("prohibited_actions") or [])
        for action in ("customer charging", "external delivery", "autonomous release"):
            require(action in prohibited, f"{profile_id}: internal_only policy must prohibit {action}")

    if profile_class == "connector" and (spec.get("write_capabilities") or []):
        require(spec.get("authority_requirements"), f"{profile_id}: write-capable connector requires authority requirements")

    return profile_id


def validate_index(root: Path, seen_ids: set[str]) -> None:
    index_path = root / "config" / "profiles" / "index.json"
    index = load_json(index_path)
    require(index.get("schema") == "dio.profile_index.v1", "unexpected profile index schema")
    entries = index.get("profiles")
    require(isinstance(entries, list), "profile index profiles must be a list")
    indexed_ids = [str(item.get("profile_id") or "") for item in entries]
    require(len(indexed_ids) == len(set(indexed_ids)), "duplicate profile IDs in profile index")
    require(set(indexed_ids) == seen_ids, "profile index does not exactly match concrete profile files")

    for entry in entries:
        profile_id = str(entry.get("profile_id") or "")
        path = (root / str(entry.get("path") or "")).resolve()
        require(path.is_relative_to(root.resolve()), f"{profile_id}: indexed path escapes repository root")
        require(path.is_file(), f"{profile_id}: indexed profile path missing")
        profile = load_json(path)
        require(profile.get("profile_id") == profile_id, f"{profile_id}: index/profile ID mismatch")
        require(profile.get("profile_class") == entry.get("profile_class"), f"{profile_id}: index/profile class mismatch")
        require(profile.get("profile_version") == entry.get("profile_version"), f"{profile_id}: index/profile version mismatch")
        require(profile.get("status") == entry.get("status"), f"{profile_id}: index/profile status mismatch")
        expected_hash = str(entry.get("content_hash") or "")
        require(expected_hash == f"sha256:{sha256_file(path)}", f"{profile_id}: profile index content hash mismatch")


def validate(root: Path) -> list[str]:
    checks: list[str] = []
    schema = load_json(root / "schemas" / "dio_profile.schema.json")
    require(schema.get("$id") == "dio.profile.v1", "unexpected profile schema id")
    require(set(((schema.get("properties") or {}).get("profile_class") or {}).get("enum") or []) == set(PROFILE_CLASS_DIRS.values()), "profile schema classes disagree with Phase 0 registry")
    checks.append("canonical profile schema present")

    profile_root = root / "config" / "profiles"
    seen_ids: set[str] = set()
    for dirname, expected_class in PROFILE_CLASS_DIRS.items():
        directory = profile_root / dirname
        require(directory.is_dir(), f"missing profile directory: {directory}")
        files = sorted(directory.glob("*.json"))
        require(files, f"profile class has no concrete instances: {dirname}")
        for path in files:
            profile_id = validate_profile(root, path, expected_class)
            require(profile_id not in seen_ids, f"duplicate profile_id: {profile_id}")
            seen_ids.add(profile_id)
    checks.append("six profile classes contain source-bound instances")

    missing_reference = EXPECTED_REFERENCE_PROFILES.difference(seen_ids)
    require(not missing_reference, f"missing Phase 1 reference profiles: {sorted(missing_reference)}")
    checks.append("Obligation-family reference profile set complete")

    validate_index(root, seen_ids)
    checks.append("profile index hashes match concrete profile bytes")

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIO Phase 1 profile foundation.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    try:
        checks = validate(args.root.resolve())
    except ProfileError as exc:
        print(f"DIO_PROFILE_FOUNDATION_REFUSE: {exc}", file=sys.stderr)
        return 1

    for check in checks:
        print(f"ALLOW {check}")
    print("DIO_PROFILE_FOUNDATION_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
