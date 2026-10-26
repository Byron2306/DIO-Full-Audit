"""M2 Phase 0 commercial constitution and existing-system harvest.

This phase creates no commercial execution engine. It inventories existing DIO
commercial organs, freezes stricter truth/authority laws, detects legacy semantic
hazards, and requires a verified M1 parent before M2 contracts are introduced.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


M2_PHASE0_EXIT_TOKEN = "DIO_M2_COMMERCIAL_CONSTITUTION_FROZEN"
DEFAULT_CONFIG = "config/m2_commercial_constitution.json"

REQUIRED_LAWS = (
    "market_research_never_implies_wtp",
    "zero_value_flow_never_implies_revenue",
    "self_payment_never_implies_independent_demand",
    "verified_payment_never_implies_customer_acceptance",
    "verified_payment_never_implies_wtp_without_independent_acceptance",
    "customer_acceptance_never_implies_repeatability",
    "commercial_success_never_mints_authority",
    "commercial_failure_never_globally_invalidates_product",
    "silence_is_evidence_only_in_exact_context",
    "market_command_never_owns_egress_authority",
    "seraph_owns_commercial_egress_boundary",
    "no_market_crystal_before_commercial_settlement",
    "commercial_learning_never_directly_executes_publishes_or_spends",
    "customer_lineage_and_payment_lineage_remain_distinct",
    "commercial_facts_are_world_state_bound",
)

REQUIRED_ANCHOR_IDS = {
    "m1_parent_proof",
    "commercial_truth_layer",
    "commercial_proof_v1_1",
    "commercial_proof_legacy_doc",
    "paid_reference_products",
    "vesper_outlook_draft_bridge",
    "commercial_operating_plan",
    "commerce_orchestrator",
    "commerce_triune",
    "commerce_event_processor",
    "dio_edge_gateway",
    "market_command_core",
    "market_command_intelligence",
    "market_command_status",
    "nichefoundry_lingua_learning",
    "lingua_lifecycle",
    "sensorium_episode",
    "beast_crystal_chain",
    "seraph_outbound_gate",
    "legalis",
    "world_lease",
    "world_settlement",
}

ALLOWED_CLASSIFICATIONS = {
    "parent_proof",
    "truth_semantics",
    "truth_evaluator",
    "legacy_semantic_hazard",
    "controlled_reference",
    "draft_only_customer_interface",
    "workflow_doctrine",
    "workflow_state",
    "workflow_advisory",
    "payment_materialisation",
    "payment_verification",
    "planning_state",
    "observation_attribution",
    "integration_status",
    "semantic_learning_doctrine",
    "semantic_lifecycle",
    "observation",
    "evidence_crystallisation",
    "authority_owner",
    "prerequisite_evaluator",
    "world_binding",
    "settlement",
}


class CommercialConstitutionError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialConstitutionError(f"cannot load M2 constitution source: {path}") from exc
    if not isinstance(value, dict):
        raise CommercialConstitutionError("M2 constitution source must be an object")
    return value


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _anchor_inventory(root: Path, config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    rows = config.get("anchors")
    if not isinstance(rows, list) or not rows:
        raise CommercialConstitutionError("M2 constitution requires anchors")

    inventory: list[dict[str, Any]] = []
    missing: list[str] = []
    invalid: list[str] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            invalid.append("non_object_anchor")
            continue
        anchor_id = str(row.get("id") or "").strip()
        rel = str(row.get("path") or "").strip()
        classification = str(row.get("classification") or "").strip()
        owner = str(row.get("owner") or "").strip()
        if not anchor_id or not rel or not owner or classification not in ALLOWED_CLASSIFICATIONS:
            invalid.append(anchor_id or rel or "unnamed_anchor")
            continue
        if anchor_id in seen_ids:
            invalid.append(f"duplicate_id:{anchor_id}")
            continue
        if rel in seen_paths:
            invalid.append(f"duplicate_path:{rel}")
            continue
        seen_ids.add(anchor_id)
        seen_paths.add(rel)
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        inventory.append(
            {
                "id": anchor_id,
                "path": rel,
                "classification": classification,
                "owner": owner,
                "digest": _file_digest(path),
            }
        )

    absent_ids = sorted(REQUIRED_ANCHOR_IDS - seen_ids)
    invalid.extend(f"missing_anchor_id:{value}" for value in absent_ids)
    return inventory, missing, invalid


def _hazard_inventory(root: Path, config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    hazards = config.get("legacy_semantic_hazards")
    if not isinstance(hazards, list) or not hazards:
        raise CommercialConstitutionError("M2 constitution requires explicit legacy semantic hazards")

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for spec in hazards:
        if not isinstance(spec, dict):
            failures.append("non_object_hazard")
            continue
        hazard_id = str(spec.get("id") or "").strip()
        source_rel = str(spec.get("path") or "").strip()
        quarantine_rel = str(spec.get("quarantined_by") or "").strip()
        must_detect = str(spec.get("must_detect") or "")
        correction = str(spec.get("required_correction") or "")
        source = root / source_rel
        quarantine = root / quarantine_rel
        if not hazard_id or not source.is_file() or not quarantine.is_file():
            failures.append(hazard_id or source_rel or "invalid_hazard")
            continue
        source_text = source.read_text(encoding="utf-8")
        quarantine_text = quarantine.read_text(encoding="utf-8")
        detected = must_detect in source_text
        corrected = correction in quarantine_text
        state = "DETECTED_QUARANTINED" if detected and corrected else "UNSAFE"
        if state != "DETECTED_QUARANTINED":
            failures.append(hazard_id)
        results.append(
            {
                "id": hazard_id,
                "state": state,
                "legacy_path": source_rel,
                "legacy_digest": _file_digest(source),
                "quarantined_by": quarantine_rel,
                "quarantine_digest": _file_digest(quarantine),
                "legacy_semantics_detected": detected,
                "required_correction_present": corrected,
            }
        )
    return results, failures


def _truth_guard_checks(root: Path) -> dict[str, bool]:
    truth = (root / "docs/DIO_COMMERCIAL_TRUTH_LAYER_PHASE10.md").read_text(encoding="utf-8")
    proof = (root / "products/commercial_proof_v1_1.py").read_text(encoding="utf-8")
    paid_reference = (root / "docs/DIO_PAID_REFERENCE_PRODUCTS_PHASE11.md").read_text(encoding="utf-8")
    vesper = (root / "docs/DIO_PHASE11_1_VESPER_ATTACHMENT_DELIVERY.md").read_text(encoding="utf-8")
    niche = (root / "docs/NICHEFOUNDRY_LINGUA_COMMERCIAL_LEARNING.md").read_text(encoding="utf-8")
    market_core = (root / "market_command/core.py").read_text(encoding="utf-8")
    edge = (root / "edge/dio-edge-gateway/src/index.js").read_text(encoding="utf-8")
    legalis = (root / "docs/DIO_LEGALIS.md").read_text(encoding="utf-8")

    return {
        "payment_proves_payment_only": "Payment proves payment only." in truth,
        "one_customer_not_repeatability": "One positive customer case does not prove repeatability." in truth,
        "commercial_evidence_not_authority": "Commercial evidence never changes maturity or creates authority." in truth,
        "verified_payment_wtp_requires_independent_acceptance": (
            "INDEPENDENT_CUSTOMER_ACCEPTANCE_REQUIRED" in proof
            and "operator/self-payment" in proof
            and "WTP_UNPROVED" in proof
        ),
        "controlled_reference_not_market_validation": "no market validation is claimed" in paid_reference,
        "vesper_outlook_remains_draft_only": (
            "DRAFT_ONLY" in vesper
            and "send_authorized: false" in vesper
            and "sent: false" in vesper
        ),
        "learning_has_no_direct_execution_path": "There is **no direct learning → execution path**." in niche,
        "market_command_automatic_spend_off": '"automatic_spend": "off"' in market_core,
        "edge_redirect_not_payment_truth": (
            "does not mark" in edge.lower() or "webhook" in edge.lower()
        ),
        "legalis_not_external_release_authority": "external action still requires its own explicit execution/release authority" in legalis,
    }


def _authority_checks(config: Mapping[str, Any]) -> dict[str, bool]:
    rows = {str(row.get("id")): row for row in (config.get("anchors") or []) if isinstance(row, dict)}
    return {
        "seraph_is_egress_authority_owner": rows.get("seraph_outbound_gate", {}).get("classification") == "authority_owner",
        "market_command_is_not_authority_owner": rows.get("market_command_core", {}).get("classification") == "planning_state",
        "vesper_is_draft_only_customer_interface": rows.get("vesper_outlook_draft_bridge", {}).get("classification") == "draft_only_customer_interface",
        "legalis_is_prerequisite_not_egress": rows.get("legalis", {}).get("classification") == "prerequisite_evaluator",
        "beast_crystals_are_evidence_not_egress": rows.get("beast_crystal_chain", {}).get("classification") == "evidence_crystallisation",
        "world_settlement_is_separate": rows.get("world_settlement", {}).get("classification") == "settlement",
    }


def validate_commercial_constitution(
    repo_root: str | Path,
    *,
    verify_m1_parent: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    config = _load_json(root / DEFAULT_CONFIG)
    if config.get("schema") != "dio.m2.commercial_constitution.v1":
        raise CommercialConstitutionError("unsupported M2 commercial constitution schema")

    laws = tuple(str(value) for value in (config.get("laws") or ()))
    law_exact = laws == REQUIRED_LAWS
    law_unique = len(laws) == len(set(laws))

    anchors, missing, invalid = _anchor_inventory(root, config)
    hazards, hazard_failures = _hazard_inventory(root, config)
    truth_guards = _truth_guard_checks(root)
    authority = _authority_checks(config)

    m1_receipt: dict[str, Any] = {
        "passed": False,
        "acceptance": "NOT_CHECKED",
    }
    if verify_m1_parent:
        from metamorphic.crystallisation import phase9_m1_receipt

        m1_receipt = phase9_m1_receipt(root)
    m1_parent_verified = (
        (not verify_m1_parent)
        or (
            m1_receipt.get("passed") is True
            and m1_receipt.get("acceptance") == config.get("m1_required_acceptance")
        )
    )

    classifications = {row["id"]: row["classification"] for row in anchors}
    constitution_payload = {
        "schema": config["schema"],
        "m1_required_acceptance": config["m1_required_acceptance"],
        "m2_final_acceptance": config["m2_final_acceptance"],
        "reference_product": config["reference_product"],
        "laws": list(laws),
        "anchors": [
            {
                "id": row["id"],
                "path": row["path"],
                "classification": row["classification"],
                "digest": row["digest"],
            }
            for row in sorted(anchors, key=lambda item: item["id"])
        ],
        "legacy_semantic_hazards": hazards,
    }
    constitution_fingerprint = _canonical_digest(constitution_payload)

    passed = (
        m1_parent_verified
        and law_exact
        and law_unique
        and len(anchors) == len(REQUIRED_ANCHOR_IDS)
        and not missing
        and not invalid
        and not hazard_failures
        and all(row.get("state") == "DETECTED_QUARANTINED" for row in hazards)
        and all(truth_guards.values())
        and all(authority.values())
    )

    return {
        "phase": "M2-0",
        "acceptance": M2_PHASE0_EXIT_TOKEN if passed else "DIO_M2_COMMERCIAL_CONSTITUTION_BLOCKED",
        "passed": passed,
        "m1_parent_required": True,
        "m1_parent_acceptance": m1_receipt.get("acceptance"),
        "m1_parent_verified": m1_parent_verified,
        "reference_product": config.get("reference_product"),
        "constitution_fingerprint": constitution_fingerprint,
        "law_count": len(laws),
        "laws_exact": law_exact,
        "laws_unique": law_unique,
        "laws": list(laws),
        "anchor_count": len(anchors),
        "missing_anchors": missing,
        "invalid_anchors": invalid,
        "anchor_classifications": classifications,
        "anchors": anchors,
        "legacy_semantic_hazards": hazards,
        "legacy_semantic_hazard_failures": hazard_failures,
        "truth_guard_checks": truth_guards,
        "authority_checks": authority,
        "market_command_is_egress_authority": False,
        "seraph_owns_egress_boundary": True,
        "payment_is_wtp": False,
        "payment_is_customer_acceptance": False,
        "self_payment_is_independent_demand": False,
        "commercial_success_mints_authority": False,
        "market_crystal_before_settlement_allowed": False,
        "commercial_learning_direct_execution_allowed": False,
        "new_runtime_engine_created": False,
        "external_effects": False,
        "authority_created": False,
        "authority_widened": False,
        "m2_final_acceptance": config.get("m2_final_acceptance"),
        "m2_final_verified": False,
    }
