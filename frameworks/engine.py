from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from products.governed_case import add_requirement, stable_id, validate_case

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "config" / "dio_framework_catalog.json"
SCHEMA_PATH = ROOT / "schemas" / "dio_framework_catalog.schema.json"
CATALOG_SCHEMA = "dio.framework.catalog.v1"


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    resolved = (path or CATALOG_PATH).expanduser().resolve()
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    validate_catalog(payload)
    return payload


def validate_catalog(catalog: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(catalog)
    if catalog.get("schema") != CATALOG_SCHEMA:
        raise ValueError(f"Expected {CATALOG_SCHEMA}.")

    frameworks = catalog.get("frameworks") or []
    ids = [str(row["framework_id"]) for row in frameworks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate framework_id in catalog.")

    for framework in frameworks:
        rules = framework.get("requirements") or []
        rule_ids = [str(row["rule_id"]) for row in rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError(f"Duplicate rule_id in {framework['framework_id']}.")
        known = set(rule_ids)
        for rule in rules:
            missing = [item for item in rule["dependency_rule_ids"] if item not in known]
            if missing:
                raise ValueError(
                    f"Unknown dependency rule(s) in {framework['framework_id']}:{rule['rule_id']}: {missing}"
                )
        _topological_rules(framework)


def _topological_rules(framework: dict[str, Any]) -> list[dict[str, Any]]:
    rules = {str(row["rule_id"]): row for row in framework.get("requirements") or []}
    pending = set(rules)
    ordered: list[dict[str, Any]] = []
    resolved: set[str] = set()
    while pending:
        ready = sorted(
            rule_id
            for rule_id in pending
            if set(rules[rule_id].get("dependency_rule_ids") or []).issubset(resolved)
        )
        if not ready:
            raise ValueError(f"Framework dependency cycle detected: {framework['framework_id']}")
        for rule_id in ready:
            ordered.append(rules[rule_id])
            resolved.add(rule_id)
            pending.remove(rule_id)
    return ordered


def framework_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_catalog(catalog)
    return {str(row["framework_id"]): row for row in catalog["frameworks"]}


def select_frameworks(
    catalog: dict[str, Any], *, product: str | None = None,
    capabilities: list[str] | None = None, jurisdiction: str | None = None,
) -> list[str]:
    capabilities = list(dict.fromkeys(capabilities or []))
    selected: list[str] = []
    for framework in catalog["frameworks"]:
        scope = framework["scope"]
        product_match = bool(product and product in scope["products"])
        capability_match = bool(set(capabilities).intersection(scope["capabilities"]))
        jurisdiction_match = bool(jurisdiction and jurisdiction in scope["jurisdictions"])
        if product_match or capability_match or jurisdiction_match:
            selected.append(str(framework["framework_id"]))
    return selected


def _source_ref(framework: dict[str, Any], rule: dict[str, Any]) -> str:
    return (
        f"framework://{framework['framework_id']}@{framework['version']}"
        f"/{rule['rule_id']}?source={framework['source_system']}:{framework['source_ref']}"
    )


def _requirement_id(case: dict[str, Any], framework: dict[str, Any], rule: dict[str, Any]) -> str:
    return stable_id(
        "REQ",
        case["case_id"],
        rule["kind"],
        _source_ref(framework, rule),
        rule["statement"],
    )


def apply_frameworks(
    case: dict[str, Any], *, framework_ids: list[str], catalog: dict[str, Any] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Normalize framework rules into Governed Case requirements.

    This function deliberately cannot create or alter gates, decisions, actors,
    capability leases or execution receipts. Framework rules are requirements,
    never authority.
    """
    catalog = catalog or load_catalog()
    index = framework_index(catalog)
    requested = list(dict.fromkeys(framework_ids))
    unknown = [item for item in requested if item not in index]
    if unknown:
        raise ValueError(f"Unknown DIO framework IDs: {unknown}")

    before_gates = json.loads(json.dumps(case["gates"], sort_keys=True))
    before_actions = json.loads(json.dumps(case["actions"], sort_keys=True))
    before_decisions = json.loads(json.dumps(case["decisions"], sort_keys=True))
    moment = _parse_time(as_of)
    applied: list[dict[str, Any]] = []

    for framework_id in requested:
        framework = index[framework_id]
        rule_to_requirement_id = {
            str(rule["rule_id"]): _requirement_id(case, framework, rule)
            for rule in framework["requirements"]
        }
        generated: list[dict[str, Any]] = []
        for rule in _topological_rules(framework):
            due_at = None
            expires_at = None
            if rule.get("due_offset_days") is not None:
                due_at = (moment + timedelta(days=int(rule["due_offset_days"]))).isoformat()
            if rule.get("expires_after_days") is not None:
                expires_at = (moment + timedelta(days=int(rule["expires_after_days"]))).isoformat()
            dependency_ids = [rule_to_requirement_id[item] for item in rule["dependency_rule_ids"]]
            row = add_requirement(
                case,
                statement=str(rule["statement"]),
                kind=str(rule["kind"]),
                source_ref=_source_ref(framework, rule),
                mandatory=bool(rule["mandatory"]),
                dependency_ids=dependency_ids,
                due_at=due_at,
                expires_at=expires_at,
            )
            generated.append(
                {
                    "rule_id": rule["rule_id"],
                    "requirement_id": row["requirement_id"],
                    "evidence_types": list(rule["evidence_types"]),
                    "authority_role": rule["authority_role"],
                    "state": row["state"],
                }
            )

        if framework_id not in case["scope"]["framework_ids"]:
            case["scope"]["framework_ids"].append(framework_id)
        applied.append(
            {
                "framework_id": framework_id,
                "version": framework["version"],
                "source_system": framework["source_system"],
                "source_ref": framework["source_ref"],
                "requirements": generated,
            }
        )

    if before_gates != json.loads(json.dumps(case["gates"], sort_keys=True)):
        raise RuntimeError("Framework application illegally mutated case gates.")
    if before_actions != json.loads(json.dumps(case["actions"], sort_keys=True)):
        raise RuntimeError("Framework application illegally mutated case actions.")
    if before_decisions != json.loads(json.dumps(case["decisions"], sort_keys=True)):
        raise RuntimeError("Framework application illegally mutated case decisions.")

    validate_case(case)
    return {
        "schema": "dio.framework.application_receipt.v1",
        "case_id": case["case_id"],
        "catalog_id": catalog["catalog_id"],
        "applied_at": moment.isoformat(),
        "frameworks": applied,
        "authority_created": False,
        "execution_performed": False,
    }


def evaluate_frameworks(
    case: dict[str, Any], *, framework_ids: list[str], catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    index = framework_index(catalog)
    reqs = {str(row["requirement_id"]): row for row in case["requirements"]}
    results: list[dict[str, Any]] = []
    blocking_states = {"unknown", "evidence_needed", "challenged", "refused", "expired"}

    for framework_id in list(dict.fromkeys(framework_ids)):
        if framework_id not in index:
            raise ValueError(f"Unknown DIO framework ID: {framework_id}")
        framework = index[framework_id]
        rules: list[dict[str, Any]] = []
        for rule in _topological_rules(framework):
            requirement_id = _requirement_id(case, framework, rule)
            row = reqs.get(requirement_id)
            state = str(row["state"]) if row else "unknown"
            rules.append(
                {
                    "rule_id": rule["rule_id"],
                    "requirement_id": requirement_id,
                    "mandatory": bool(rule["mandatory"]),
                    "state": state,
                    "satisfied_for_framework": state in {"supported", "satisfied", "waived"},
                    "authority_role": rule["authority_role"],
                    "evidence_types": list(rule["evidence_types"]),
                }
            )
        mandatory_blockers = [
            row["rule_id"] for row in rules
            if row["mandatory"] and row["state"] in blocking_states
        ]
        results.append(
            {
                "framework_id": framework_id,
                "state": "READY" if not mandatory_blockers else "NOT_READY",
                "mandatory_blockers": mandatory_blockers,
                "rules": rules,
            }
        )

    return {
        "schema": "dio.framework.evaluation.v1",
        "case_id": case["case_id"],
        "frameworks": results,
        "overall_state": "READY" if all(row["state"] == "READY" for row in results) else "NOT_READY",
        "authority_created": False,
        "execution_performed": False,
    }
