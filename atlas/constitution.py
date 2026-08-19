"""DIO ATLAS M4 constitutional freeze.

This module validates the semantic/authority laws of ATLAS without expanding the
execution-grade Metamorphic Registry. It is intentionally filesystem/source bound
and creates no runtime engine or external effect.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ATLAS_CONSTITUTION_TOKEN = "DIO_ATLAS_M4_CONSTITUTION_FROZEN"
ATLAS_CONSTITUTION_BLOCKED = "DIO_ATLAS_M4_CONSTITUTION_BLOCKED"
DEFAULT_ATLAS_CONSTITUTION = "config/atlas/dio_atlas_constitution.json"

REQUIRED_LAWS = (
    "knowledge_never_implies_capability",
    "similarity_never_implies_equivalence",
    "analogy_never_implies_evidence",
    "domain_adjacency_never_implies_market_demand",
    "task_match_never_implies_execution_proof",
    "taxonomy_membership_never_mints_authority",
    "commercial_negative_learning_never_globally_invalidates_product",
    "negative_learning_may_generate_pivot_hypothesis_but_never_execute_it",
    "verified_capability_identity_must_be_preserved_across_domain_projection",
    "capability_gaps_must_remain_explicit",
    "external_taxonomy_nodes_are_knowledge_only_until_separately_proved",
    "all_cross_domain_relations_require_provenance_and_relation_state",
    "governed_review_required_before_analogical_candidate_becomes_semantic_policy",
    "authority_ceiling_cannot_widen_during_pivot",
    "commercial_truth_remains_context_bound",
    "unknown_domain_names_must_not_block_task_morphology_reasoning",
)

REQUIRED_RELATION_STATES = (
    "SOURCE_ASSERTED",
    "CROSSWALKED",
    "DIO_DERIVED",
    "ANALOGICAL_CANDIDATE",
    "HUMAN_APPROVED",
    "EXECUTION_CORROBORATED",
    "MARKET_CORROBORATED",
)

REQUIRED_MECHANICAL_VERDICTS = (
    "COMPOSABLE",
    "PARTIALLY_COMPOSABLE",
    "UNSUPPORTED",
)


class AtlasConstitutionError(RuntimeError):
    pass


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_ATLAS_CONSTITUTION
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AtlasConstitutionError(f"cannot load ATLAS constitution: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "dio.atlas.m4_constitution.v1":
        raise AtlasConstitutionError("unsupported ATLAS constitution")
    return payload


def validate_atlas_constitution(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    payload = _load(root)
    laws = tuple(str(value) for value in payload.get("laws") or ())
    relation_states = tuple(str(value) for value in payload.get("relation_states") or ())
    mechanical_verdicts = tuple(str(value) for value in payload.get("mechanical_verdicts") or ())
    source_files = payload.get("source_files")
    if not isinstance(source_files, dict) or not source_files:
        raise AtlasConstitutionError("ATLAS constitution requires source_files")
    source_digests: dict[str, str] = {}
    missing: list[str] = []
    for source_id, rel in source_files.items():
        path = root / str(rel)
        if not path.is_file():
            missing.append(str(rel))
            continue
        source_digests[str(source_id)] = _digest(path)

    truth_boundaries = {
        "source_knowledge_may_create_capability": payload.get("source_knowledge_may_create_capability") is False,
        "source_knowledge_may_create_authority": payload.get("source_knowledge_may_create_authority") is False,
        "analogical_resolution_may_execute": payload.get("analogical_resolution_may_execute") is False,
        "negative_learning_may_execute_pivot": payload.get("negative_learning_may_execute_pivot") is False,
        "capability_cost_is_first_class": payload.get("capability_cost_is_first_class") is True,
        "m3_boundary_must_remain_preserved": payload.get("m3_boundary_must_remain_preserved") is True,
        "foundation_not_final": payload.get("m4_0_is_foundation_not_final_verification") is True,
    }
    passed = (
        laws == REQUIRED_LAWS
        and relation_states == REQUIRED_RELATION_STATES
        and mechanical_verdicts == REQUIRED_MECHANICAL_VERDICTS
        and not missing
        and len(source_digests) == len(source_files)
        and all(truth_boundaries.values())
        and payload.get("required_parent_acceptance") == "DIO_METAMORPHIC_COMMERCIAL_METABOLISM_VERIFIED"
        and payload.get("m4_final_acceptance") == "DIO_ATLAS_UNIVERSAL_PIVOT_VERIFIED"
    )
    return {
        "schema": "dio.atlas.m4_constitution_receipt.v1",
        "phase": "M4-0C",
        "acceptance": ATLAS_CONSTITUTION_TOKEN if passed else ATLAS_CONSTITUTION_BLOCKED,
        "passed": passed,
        "required_parent_acceptance": payload.get("required_parent_acceptance"),
        "m4_final_acceptance": payload.get("m4_final_acceptance"),
        "law_count": len(laws),
        "laws_exact": laws == REQUIRED_LAWS,
        "relation_state_count": len(relation_states),
        "relation_states_exact": relation_states == REQUIRED_RELATION_STATES,
        "mechanical_verdict_count": len(mechanical_verdicts),
        "mechanical_verdicts_exact": mechanical_verdicts == REQUIRED_MECHANICAL_VERDICTS,
        "source_file_count": len(source_files),
        "source_digests": source_digests,
        "missing_source_files": missing,
        "minimums": payload.get("minimums"),
        "exact_portfolio_bindings": payload.get("exact_portfolio_bindings"),
        "truth_boundaries": truth_boundaries,
        "full_external_taxonomy_ingestion_required_for_m4_0": payload.get("full_external_taxonomy_ingestion_required_for_m4_0") is True,
        "federation_envelope_may_reference_not_yet_ingested_sources": payload.get("federation_envelope_may_reference_not_yet_ingested_sources") is True,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m4_final_verified": False,
    }


__all__ = [
    "ATLAS_CONSTITUTION_BLOCKED",
    "ATLAS_CONSTITUTION_TOKEN",
    "AtlasConstitutionError",
    "DEFAULT_ATLAS_CONSTITUTION",
    "REQUIRED_LAWS",
    "REQUIRED_MECHANICAL_VERDICTS",
    "REQUIRED_RELATION_STATES",
    "validate_atlas_constitution",
]
