from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


COMPILER_SCHEMA = "dio.compiled_product.v1"
COMPILER_VERSION = "1.1.0"
COMPILER_SOURCE_REF = "products/compiler.py"
MANIFEST_ROOT = Path("config/products/manifests")
PROFILE_KEY_TO_CLASS = {
    "domain": "domain",
    "framework": "framework",
    "authority": "authority",
    "connector_pack": "connector",
    "output": "output",
    "commercial": "commercial",
}


class CompilerError(RuntimeError):
    pass


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompilerError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CompilerError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CompilerError(f"expected JSON object: {path}")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CompilerError(message)


def validate_manifest_schema(root: Path, manifest: dict[str, Any]) -> None:
    schema = load_json(root / "schemas" / "dio_product_manifest.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda err: list(err.absolute_path))
    if errors:
        rendered = []
        for error in errors[:12]:
            where = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{where}: {error.message}")
        raise CompilerError("manifest schema validation failed: " + " | ".join(rendered))


def validate_compiled_schema(root: Path, compiled: dict[str, Any]) -> None:
    schema = load_json(root / "schemas" / "dio_compiled_product.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(compiled), key=lambda err: list(err.absolute_path))
    if errors:
        rendered = []
        for error in errors[:12]:
            where = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{where}: {error.message}")
        raise CompilerError("compiled product schema validation failed: " + " | ".join(rendered))


def load_manifest_registry(root: Path) -> dict[str, dict[str, Any]]:
    manifest_root = (root / MANIFEST_ROOT).resolve()
    require(manifest_root.is_dir(), f"canonical manifest directory missing: {manifest_root}")
    result: dict[str, dict[str, Any]] = {}
    incarnations: dict[str, str] = {}
    for path in sorted(manifest_root.glob("*.json")):
        manifest = load_json(path)
        validate_manifest_schema(root, manifest)
        product_id = str(manifest.get("product_id") or "")
        incarnation_id = str((manifest.get("incarnation") or {}).get("id") or "")
        require(product_id not in result, f"duplicate canonical product_id: {product_id}")
        require(incarnation_id not in incarnations, f"duplicate canonical incarnation id: {incarnation_id}")
        require(path.stem == incarnation_id, f"manifest filename must equal incarnation id: {path.name} != {incarnation_id}.json")
        result[product_id] = {
            "path": str(path),
            "manifest": manifest,
            "incarnation_id": incarnation_id,
        }
        incarnations[incarnation_id] = product_id
    require(result, "canonical manifest registry is empty")
    return result


def load_profile_index(root: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(root / "config" / "profiles" / "index.json")
    require(payload.get("schema") == "dio.profile_index.v1", "unexpected profile index schema")
    rows = payload.get("profiles")
    require(isinstance(rows, list), "profile index profiles must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        require(isinstance(row, dict), "profile index row must be an object")
        profile_id = str(row.get("profile_id") or "")
        require(profile_id, "profile index row missing profile_id")
        require(profile_id not in result, f"duplicate profile in index: {profile_id}")
        path = (root / str(row.get("path") or "")).resolve()
        require(path.is_relative_to(root.resolve()), f"profile path escapes repository: {profile_id}")
        require(path.is_file(), f"profile path missing: {profile_id}")
        expected_hash = str(row.get("content_hash") or "")
        require(expected_hash == f"sha256:{sha256_file(path)}", f"stale profile index hash: {profile_id}")
        result[profile_id] = {**row, "resolved_path": str(path)}
    return result


def bind_profiles(
    root: Path,
    manifest: dict[str, Any],
    index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    bindings: list[dict[str, Any]] = []
    loaded: dict[str, dict[str, Any]] = {}
    profile_groups = manifest.get("profiles") or {}
    for manifest_key, expected_class in PROFILE_KEY_TO_CLASS.items():
        refs = profile_groups.get(manifest_key) or []
        require(isinstance(refs, list) and refs, f"manifest profile group {manifest_key} must not be empty")
        for ref in refs:
            profile_id = str(ref.get("profile_id") or "")
            require(ref.get("binding") == "BOUND", f"profile reference must be BOUND: {profile_id}")
            indexed = index.get(profile_id)
            require(indexed is not None, f"profile not found in canonical index: {profile_id}")
            require(indexed.get("profile_class") == expected_class, f"profile class mismatch for {profile_id}")
            require(indexed.get("profile_version") == ref.get("version"), f"profile version mismatch for {profile_id}")
            require(indexed.get("content_hash") == ref.get("content_hash"), f"profile content hash mismatch for {profile_id}")
            profile_path = Path(str(indexed["resolved_path"]))
            profile = load_json(profile_path)
            require(profile.get("profile_id") == profile_id, f"profile file identity mismatch: {profile_id}")
            bindings.append(
                {
                    "manifest_key": manifest_key,
                    "profile_class": expected_class,
                    "profile_id": profile_id,
                    "profile_version": indexed["profile_version"],
                    "content_hash": indexed["content_hash"],
                    "status": indexed.get("status"),
                    "path": str(profile_path.relative_to(root)),
                }
            )
            loaded[profile_id] = profile
    bindings.sort(key=lambda item: (item["profile_class"], item["profile_id"]))
    return bindings, loaded


def load_work_patterns(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    path = root / "config" / "portfolio" / "work_patterns.json"
    payload = load_json(path)
    rows = payload.get("work_patterns") or []
    result = {str(row["id"]): row for row in rows}
    require(len(result) == len(rows), "duplicate work pattern IDs")
    return result, f"sha256:{sha256_file(path)}"


def load_meta_capabilities(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    path = root / "config" / "portfolio" / "meta_capabilities.json"
    payload = load_json(path)
    rows = payload.get("meta_capabilities") or []
    result = {str(row["id"]): row for row in rows}
    require(len(result) == 4, "META registry must contain exactly four capabilities")
    return result, f"sha256:{sha256_file(path)}"


def validate_pattern_meta_composition(
    manifest: dict[str, Any],
    patterns: dict[str, dict[str, Any]],
    meta: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected_patterns: list[dict[str, Any]] = []
    required_meta: set[str] = set()
    for pattern_id in manifest.get("work_patterns") or []:
        pattern = patterns.get(str(pattern_id))
        require(pattern is not None, f"unknown work pattern: {pattern_id}")
        selected_patterns.append(copy.deepcopy(pattern))
        required_meta.update(str(item) for item in pattern.get("primary_meta") or [])

    selected_meta_ids = set(str(item) for item in manifest.get("meta_capabilities") or [])
    missing = required_meta.difference(selected_meta_ids)
    require(not missing, f"META composition incomplete for selected work patterns: {sorted(missing)}")

    selected_meta: list[dict[str, Any]] = []
    for meta_id in sorted(selected_meta_ids):
        item = meta.get(meta_id)
        require(item is not None, f"unknown META capability: {meta_id}")
        selected_meta.append(copy.deepcopy(item))
    selected_patterns.sort(key=lambda item: str(item["id"]))
    return selected_patterns, selected_meta


def load_capability_catalog(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    path = root / "config" / "portfolio" / "capability_catalog.json"
    payload = load_json(path)
    require(payload.get("schema") == "dio.capability_catalog.v1", "unexpected capability catalog schema")
    laws = payload.get("laws") or {}
    require(laws.get("products_request_capabilities_not_organs") is True, "capability catalog must preserve capability-first product law")
    require(laws.get("compiler_resolves_providers") is True, "compiler must remain provider resolver")
    require(laws.get("provider_applicability_must_be_explicit") is True, "provider applicability must be explicit")
    rows = payload.get("capabilities")
    require(isinstance(rows, list), "capability catalog capabilities must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        require(isinstance(row, dict), "capability catalog row must be an object")
        capability_id = str(row.get("capability_id") or "")
        require(capability_id, "capability catalog row missing capability_id")
        require(capability_id not in result, f"duplicate capability ID: {capability_id}")
        status = str(row.get("status") or "")
        require(status in {"available", "planned", "deprecated", "disabled"}, f"invalid capability status: {capability_id}")
        providers = row.get("providers") or []
        require(isinstance(providers, list), f"providers must be a list: {capability_id}")
        provider_ids: set[str] = set()
        for provider in providers:
            provider_id = str(provider.get("provider_id") or "")
            require(provider_id and provider_id not in provider_ids, f"duplicate/empty provider for {capability_id}")
            provider_ids.add(provider_id)
            ref = str(provider.get("ref") or "")
            require(ref, f"provider ref required: {capability_id}/{provider_id}")
            product_scope = provider.get("product_scope")
            require(isinstance(product_scope, list) and product_scope, f"provider product_scope required: {capability_id}/{provider_id}")
            require(all(isinstance(item, str) and item for item in product_scope), f"provider product_scope contains invalid entry: {capability_id}/{provider_id}")
            resolved = (root / ref).resolve()
            require(resolved.is_relative_to(root.resolve()), f"provider ref escapes repository: {capability_id}/{provider_id}")
            if status == "available":
                require(resolved.is_file(), f"available provider ref missing: {capability_id}/{provider_id}: {ref}")
        if status == "available":
            require(providers, f"available capability has no providers: {capability_id}")
        result[capability_id] = row
    return result, f"sha256:{sha256_file(path)}"


def _provider_applies(provider: dict[str, Any], product_id: str) -> bool:
    scope = set(str(item) for item in provider.get("product_scope") or [])
    return "*" in scope or product_id in scope


def resolve_capability(
    requirement: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    product_id: str,
) -> dict[str, Any]:
    capability_id = str(requirement.get("capability_id") or "")
    required = bool(requirement.get("required"))
    execution_required = bool(requirement.get("execution_required"))
    definition = catalog.get(capability_id)
    if definition is None:
        return {
            "capability_id": capability_id,
            "required": required,
            "execution_required": execution_required,
            "resolution_state": "UNKNOWN",
            "provider": None,
            "reason": "Capability is absent from the canonical capability catalog.",
        }

    status = str(definition.get("status") or "")
    providers = list(definition.get("providers") or [])
    applicable = [provider for provider in providers if _provider_applies(provider, product_id)]
    eligible = [provider for provider in applicable if (not execution_required or bool(provider.get("execution_capable")))]
    eligible.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("provider_id") or "")))

    if status == "available" and eligible:
        chosen = eligible[0]
        return {
            "capability_id": capability_id,
            "required": required,
            "execution_required": execution_required,
            "resolution_state": "RESOLVED",
            "provider": {
                "provider_id": chosen["provider_id"],
                "provider_kind": chosen.get("provider_kind"),
                "ref": chosen.get("ref"),
                "execution_capable": bool(chosen.get("execution_capable")),
                "product_scope": list(chosen.get("product_scope") or []),
            },
            "reason": "Resolved deterministically from an earned provider whose product scope includes this product.",
        }

    if status == "planned":
        return {
            "capability_id": capability_id,
            "required": required,
            "execution_required": execution_required,
            "resolution_state": "PLANNED",
            "provider": None,
            "reason": "Capability is declared as planned but has not been earned by an available provider.",
        }

    if status == "available" and providers and not applicable:
        reason = "Capability exists, but no earned provider declares applicability to this product."
    elif status == "available" and execution_required and applicable and not eligible:
        reason = "Applicable providers exist, but none are execution-capable."
    else:
        reason = f"Capability status is {status or 'unknown'}."
    return {
        "capability_id": capability_id,
        "required": required,
        "execution_required": execution_required,
        "resolution_state": "UNAVAILABLE",
        "provider": None,
        "reason": reason,
    }


def commercial_release_policy(profiles: dict[str, dict[str, Any]]) -> tuple[str | None, bool]:
    offer_states: list[str] = []
    for profile in profiles.values():
        if profile.get("profile_class") != "commercial":
            continue
        offer_states.append(str((profile.get("spec") or {}).get("offer_state") or ""))
    offer_state = sorted(set(offer_states))[0] if offer_states else None
    return offer_state, offer_state == "internal_only"


def build_case_template(manifest: dict[str, Any], bindings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "dio.compiled_case_template.v1",
        "product": manifest["product_id"],
        "governed_case_schema": "dio.governed_case.v2",
        "required_profile_bindings": [item["profile_id"] for item in bindings],
        "required_work_patterns": list(manifest["work_patterns"]),
        "required_meta_capabilities": list(manifest["meta_capabilities"]),
        "case_grammar": [
            "case_identity",
            "commercial_lineage",
            "requirements",
            "claims",
            "evidence",
            "gates",
            "decisions",
            "outputs",
        ],
        "product_specific_extensions": {},
    }


def build_output_plan(profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for profile in profiles.values():
        if profile.get("profile_class") != "output":
            continue
        spec = profile.get("spec") or {}
        rows.append(
            {
                "profile_id": profile["profile_id"],
                "artifact_types": list(spec.get("artifact_types") or []),
                "required_sections": list(spec.get("required_sections") or []),
                "disclosure_rules": list(spec.get("disclosure_rules") or []),
                "qa_requirements": list(spec.get("qa_requirements") or []),
            }
        )
    rows.sort(key=lambda item: item["profile_id"])
    return {"schema": "dio.compiled_output_plan.v1", "outputs": rows}


def compile_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    root = root.resolve()
    canonical_root = (root / MANIFEST_ROOT).resolve()
    manifest_path = manifest_path.resolve()
    require(manifest_path.is_relative_to(canonical_root), "compiler accepts only manifests under config/products/manifests/")

    registry = load_manifest_registry(root)
    manifest = load_json(manifest_path)
    validate_manifest_schema(root, manifest)
    product_id = str(manifest["product_id"])
    registered = registry.get(product_id)
    require(registered is not None, f"manifest product is not present in canonical registry: {product_id}")
    require(Path(str(registered["path"])).resolve() == manifest_path, f"canonical manifest path mismatch for {product_id}")

    profile_index = load_profile_index(root)
    bindings, loaded_profiles = bind_profiles(root, manifest, profile_index)
    work_patterns, work_patterns_hash = load_work_patterns(root)
    meta_capabilities, meta_hash = load_meta_capabilities(root)
    selected_patterns, selected_meta = validate_pattern_meta_composition(manifest, work_patterns, meta_capabilities)
    capability_catalog, capability_hash = load_capability_catalog(root)

    capability_plan = [resolve_capability(requirement, capability_catalog, product_id) for requirement in manifest.get("capability_requirements") or []]
    capability_plan.sort(key=lambda item: item["capability_id"])

    unresolved_required = [item for item in capability_plan if item["required"] and item["resolution_state"] != "RESOLVED"]
    unresolved_planning = [item for item in unresolved_required if not item["execution_required"]]
    unresolved_execution = [item for item in unresolved_required if item["execution_required"]]

    maturity = copy.deepcopy(manifest["maturity"])
    executable_claimed = bool((maturity.get("operational_flags") or {}).get("executable"))
    if executable_claimed and unresolved_execution:
        raise CompilerError("manifest claims executable=true while required execution capabilities remain unresolved")

    offer_state, internal_only = commercial_release_policy(loaded_profiles)
    campaign_enabled = bool((maturity.get("operational_flags") or {}).get("campaign_enabled"))
    require(not (internal_only and campaign_enabled), "internal-only commercial profile cannot coexist with campaign_enabled=true")

    planning_state = "ALLOW" if not unresolved_planning else "NEEDS_IMPLEMENTATION"
    execution_state = "NEEDS_YOU" if executable_claimed and not unresolved_execution else "REFUSE"
    if internal_only or not campaign_enabled:
        release_state = "REFUSE"
        release_reason = "Commercial policy or maturity flags prohibit external release."
    else:
        release_state = "NEEDS_YOU"
        release_reason = "External release remains bound to explicit human authority even after compilation."

    input_receipt = {
        "manifest": {"path": str(manifest_path.relative_to(root)), "sha256": sha256_file(manifest_path)},
        "profiles": [{"profile_id": item["profile_id"], "content_hash": item["content_hash"]} for item in bindings],
        "registries": {
            "work_patterns": work_patterns_hash,
            "meta_capabilities": meta_hash,
            "capability_catalog": capability_hash,
            "profile_index": f"sha256:{sha256_file(root / 'config' / 'profiles' / 'index.json')}",
            "manifest_schema": f"sha256:{sha256_file(root / 'schemas' / 'dio_product_manifest.schema.json')}",
        },
    }
    composition_fingerprint = f"sha256:{sha256_json(input_receipt)}"
    compiler_source = Path(__file__).resolve()
    compiler_provenance = {
        "version": COMPILER_VERSION,
        "source_ref": COMPILER_SOURCE_REF,
        "source_sha256": f"sha256:{sha256_file(compiler_source)}",
    }

    execution_reason = (
        "All required execution capabilities resolve, but execution remains bound to explicit human initiation and authority."
        if execution_state == "NEEDS_YOU"
        else "Compilation does not create execution authority; unresolved or unearned execution capability remains."
    )
    compiled = {
        "schema": COMPILER_SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "compiler_provenance": compiler_provenance,
        "product_id": product_id,
        "name": manifest["name"],
        "incarnation": copy.deepcopy(manifest["incarnation"]),
        "suite_ids": list(manifest["suite_ids"]),
        "composition_fingerprint": composition_fingerprint,
        "compilation_fingerprint": "",
        "input_receipt": input_receipt,
        "work_patterns": selected_patterns,
        "meta_capabilities": selected_meta,
        "profile_bindings": bindings,
        "capability_plan": capability_plan,
        "maturity": maturity,
        "gates": {
            "composition": {"state": "ALLOW", "reason": "Manifest, profile bindings and composition invariants validated."},
            "planning": {"state": planning_state, "reason": "All required planning capabilities resolve." if planning_state == "ALLOW" else "Required planning capabilities remain unearned or inapplicable."},
            "execution": {"state": execution_state, "reason": execution_reason},
            "human_review": {"state": "NEEDS_YOU", "reason": "Consequential judgement remains human-authority bound."},
            "external_release": {"state": release_state, "reason": release_reason},
        },
        "unresolved": {
            "planning": [item["capability_id"] for item in unresolved_planning],
            "execution": [item["capability_id"] for item in unresolved_execution],
        },
        "case_template": build_case_template(manifest, bindings),
        "output_plan": build_output_plan(loaded_profiles),
        "commercial_policy": {"offer_state": offer_state, "external_release_state": release_state},
    }

    compilation_basis = copy.deepcopy(compiled)
    compilation_basis.pop("compilation_fingerprint", None)
    compilation_receipt_basis = {
        "composition_fingerprint": composition_fingerprint,
        "compiler_provenance": compiler_provenance,
        "compiled_schema_sha256": f"sha256:{sha256_file(root / 'schemas' / 'dio_compiled_product.schema.json')}",
        "compiled_plan_sha256": f"sha256:{sha256_json(compilation_basis)}",
    }
    compiled["compilation_fingerprint"] = f"sha256:{sha256_json(compilation_receipt_basis)}"
    validate_compiled_schema(root, compiled)
    return compiled


def build_test_plan(compiled: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.compiled_test_plan.v1",
        "product_id": compiled["product_id"],
        "composition_fingerprint": compiled["composition_fingerprint"],
        "compilation_fingerprint": compiled["compilation_fingerprint"],
        "required_assertions": [
            "same canonical inputs reproduce the same composition fingerprint",
            "same compiler source and canonical inputs reproduce the same compilation fingerprint",
            "profile hash drift causes compilation refusal",
            "missing required execution capability yields execution REFUSE",
            "earned execution capability yields NEEDS_YOU rather than autonomous ALLOW",
            "external release is never granted by compilation alone",
            "product manifest contains no direct organ wiring",
            "work-pattern META requirements are a subset of the product META composition",
            "an earned provider must explicitly declare applicability to the product",
            "only canonical manifests may be compiled",
        ],
        "current_expected_gates": copy.deepcopy(compiled["gates"]),
    }


def write_compilation(root: Path, compiled: dict[str, Any], output_root: Path | None = None) -> Path:
    root = root.resolve()
    validate_compiled_schema(root, compiled)
    base = (output_root or (root / "state" / "compiled_products")).resolve()
    require(base.is_relative_to(root), "compiled output root must remain inside repository root")
    target = base / compiled["product_id"]
    target.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "COMPILED_PRODUCT.json": compiled,
        "CASE_TEMPLATE.json": compiled["case_template"],
        "CAPABILITY_PLAN.json": {"schema": "dio.compiled_capability_plan.v1", "product_id": compiled["product_id"], "capabilities": compiled["capability_plan"]},
        "GATE_PLAN.json": {"schema": "dio.compiled_gate_plan.v1", "product_id": compiled["product_id"], "gates": compiled["gates"]},
        "OUTPUT_PLAN.json": compiled["output_plan"],
        "TEST_PLAN.json": build_test_plan(compiled),
        "COMPILATION_RECEIPT.json": {
            "schema": "dio.product_compilation_receipt.v1",
            "compiler_version": COMPILER_VERSION,
            "compiler_provenance": compiled["compiler_provenance"],
            "product_id": compiled["product_id"],
            "composition_fingerprint": compiled["composition_fingerprint"],
            "compilation_fingerprint": compiled["compilation_fingerprint"],
            "compiled_at": timestamp(),
            "execution_gate": compiled["gates"]["execution"]["state"],
            "external_release_gate": compiled["gates"]["external_release"]["state"],
        },
    }

    for filename, payload in artifacts.items():
        path = target / filename
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(path)
    return target


def inspect_compilation(compiled: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": compiled["product_id"],
        "name": compiled["name"],
        "composition_fingerprint": compiled["composition_fingerprint"],
        "compilation_fingerprint": compiled["compilation_fingerprint"],
        "compiler_provenance": compiled["compiler_provenance"],
        "maturity": compiled["maturity"]["state"],
        "gates": {key: value["state"] for key, value in compiled["gates"].items()},
        "resolved_capabilities": [item["capability_id"] for item in compiled["capability_plan"] if item["resolution_state"] == "RESOLVED"],
        "unresolved_planning": list(compiled["unresolved"]["planning"]),
        "unresolved_execution": list(compiled["unresolved"]["execution"]),
        "profiles": [item["profile_id"] for item in compiled["profile_bindings"]],
        "work_patterns": [item["id"] for item in compiled["work_patterns"]],
        "meta_capabilities": [item["id"] for item in compiled["meta_capabilities"]],
    }
