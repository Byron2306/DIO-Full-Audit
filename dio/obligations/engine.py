from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from products.governed_case import (
    add_requirement,
    link_evidence,
    raise_challenge,
    validate_case,
)

from .deadlines import identify_deadlines
from .evidence import bind_evidence
from .extractor import extract
from .models import BUNDLE_SCHEMA, ENGINE_VERSION, RESERVED_VERDICTS, canonical_json, sha256_json
from .normalizer import normalize
from .status import evaluate


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "dio_obligation_bundle.schema.json"
ENGINE_SOURCE_REF = "dio/obligations/engine.py"
CAPABILITY_BINDINGS = {
    "obligation.extract": "extract",
    "obligation.normalize": "normalize",
    "obligation.deadlines": "identify_deadlines",
    "obligation.evaluate": "evaluate",
}


def _fingerprint_body(bundle: dict[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(bundle)
    body.pop("fingerprint", None)
    return body


def fingerprint_bundle(bundle: dict[str, Any]) -> str:
    return f"sha256:{sha256_json(_fingerprint_body(bundle))}"


def validate_bundle(bundle: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(bundle), key=lambda err: list(err.absolute_path))
    if errors:
        rendered: list[str] = []
        for error in errors[:12]:
            where = ".".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"{where}: {error.message}")
        raise ValueError("obligation bundle schema validation failed: " + " | ".join(rendered))
    if bundle.get("schema") != BUNDLE_SCHEMA or bundle.get("engine_version") != ENGINE_VERSION:
        raise ValueError("unexpected obligation bundle identity")
    if bundle.get("authority_created") is not False:
        raise ValueError("Obligation Core may not create authority")
    if bundle.get("executor_created") is not False:
        raise ValueError("Obligation Core may not create executors")
    if bundle.get("external_effects") is not False:
        raise ValueError("Obligation Core may not perform external effects")
    if (bundle.get("human_gate") or {}).get("state") != "NEEDS_YOU":
        raise ValueError("Obligation Core must preserve the human fulfilment boundary")
    for row in bundle.get("obligations") or []:
        if str(row.get("status") or "") in RESERVED_VERDICTS:
            raise ValueError("Obligation Core emitted a reserved authority/compliance verdict")
    expected = fingerprint_bundle(bundle)
    if bundle.get("fingerprint") != expected:
        raise ValueError("obligation bundle fingerprint mismatch")


def build(
    source: dict[str, Any],
    *,
    evidence_records: list[dict[str, Any]] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Run the bounded v0.1 planning pipeline and return a tamper-evident bundle."""
    candidates = extract(source)
    bundle = normalize(source, candidates)
    identify_deadlines(bundle, now=now)
    if evidence_records is not None:
        bind_evidence(bundle, evidence_records)
    evaluate(bundle, now=now)
    bundle["fingerprint"] = fingerprint_bundle(bundle)
    validate_bundle(bundle)
    return bundle


def _authority_snapshot(case: dict[str, Any]) -> str:
    return canonical_json(
        {
            "gates": case.get("gates") or [],
            "actions": case.get("actions") or [],
            "decisions": case.get("decisions") or [],
        }
    )


def project(bundle: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Project obligations into Governed Case without minting authority.

    Projection creates requirement/deadline/evidence-link/challenge state only.
    It never changes gates, actions, decisions, execution leases or release state.
    """
    validate_bundle(bundle)
    validate_case(case)
    before_authority = _authority_snapshot(case)
    requirement_map: dict[str, str] = {}

    for obligation in bundle.get("obligations") or []:
        locator = str((obligation.get("source") or {}).get("locator") or "")
        source_ref = str((obligation.get("source") or {}).get("source_ref") or "")
        bound_source_ref = f"{source_ref}#{locator}" if locator else source_ref
        requirement = add_requirement(
            case,
            statement=str(obligation["statement"]),
            kind="obligation",
            source_ref=bound_source_ref,
            mandatory=True,
            owner_actor_id=None,
            due_at=obligation.get("due_at"),
            expires_at=obligation.get("expires_at"),
        )
        requirement_map[str(obligation["obligation_id"])] = str(requirement["requirement_id"])

    known_evidence = {str(row["evidence_id"]) for row in case.get("evidence") or []}
    for binding in bundle.get("evidence_bindings") or []:
        evidence_id = str(binding["evidence_id"])
        obligation_id = str(binding["obligation_id"])
        if evidence_id not in known_evidence:
            raise ValueError(f"obligation projection references evidence absent from Governed Case: {evidence_id}")
        requirement_id = requirement_map[obligation_id]
        if binding["relation"] == "supports":
            link_evidence(case, evidence_id=evidence_id, requirement_id=requirement_id, relation="supports")
        elif binding["trust_state"] == "trusted_for_review" and binding["freshness_state"] not in {"stale", "expired"}:
            raise_challenge(
                case,
                target_type="requirement",
                target_id=requirement_id,
                challenge_type="contradiction",
                severity="material",
                hypothesis=f"Bound evidence {evidence_id} contradicts obligation {obligation_id}.",
                raised_by="dio.obligation_core",
                evidence_ids=[evidence_id],
            )

    event_ref = f"obligation://{bundle['fingerprint']}"
    if event_ref not in case["event_refs"]:
        case["event_refs"].append(event_ref)
    validate_case(case)
    after_authority = _authority_snapshot(case)
    if before_authority != after_authority:
        raise RuntimeError("Obligation Core projection attempted to mutate authority surfaces")

    return {
        "schema": "dio.obligation_projection_receipt.v1",
        "case_id": case["case_id"],
        "bundle_fingerprint": bundle["fingerprint"],
        "requirement_map": requirement_map,
        "authority_created": False,
        "execution_performed": False,
        "external_release": False,
    }
