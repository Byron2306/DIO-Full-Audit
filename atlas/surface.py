"""Truth-safe receipts over the dynamically derived ATLAS incarnation surface.

This layer deliberately distinguishes the preserved 53-row legacy portfolio from
the much larger generated candidate surface. Gap-bearing candidates include both
PARTIALLY_COMPOSABLE_CANDIDATE and CAPABILITY_GAP states. The presence of a
candidate never creates capability, market demand, execution, or authority.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from metamorphic.contracts import digest_payload

from .incarnations import (
    LEGACY_PORTFOLIO_COUNT,
    compile_candidate_incarnations,
    eligible_domain_nodes,
    load_job_morphologies,
    rank_candidate_incarnations_from_negative_learning,
)
from .registry import AtlasRegistry


ATLAS_SURFACE_TOKEN = "DIO_ATLAS_DERIVED_PORTFOLIO_SURFACE_READY"
ATLAS_SURFACE_BLOCKED = "DIO_ATLAS_DERIVED_PORTFOLIO_SURFACE_BLOCKED"
ATLAS_SURFACE_PIVOT_TOKEN = "DIO_ATLAS_VAST_NEGATIVE_LEARNING_PIVOT_READY"
ATLAS_SURFACE_PIVOT_BLOCKED = "DIO_ATLAS_VAST_NEGATIVE_LEARNING_PIVOT_BLOCKED"


def candidate_surface_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry = AtlasRegistry.load(root)
    templates = load_job_morphologies(root, registry)
    candidates = compile_candidate_incarnations(root, registry=registry)
    eligible = eligible_domain_nodes(registry)

    state_counts = Counter(row.candidate_state for row in candidates)
    verdict_counts = Counter(row.mechanical_verdict for row in candidates)
    family_counts = Counter(row.domain_family for row in candidates)
    template_counts = Counter(row.template_id for row in candidates)
    cost_counts = Counter(row.capability_cost for row in candidates)
    covered_domains = {row.domain_id for row in candidates}
    novel = [row for row in candidates if row.legacy_analogy_count == 0]
    legacy_overlap = [row for row in candidates if row.legacy_analogy_count > 0]
    gap_bearing = [row for row in candidates if row.candidate_state != "COMPOSABLE_CANDIDATE"]
    held_truth = all(
        row.execution_truth_state == "UNPROVED_CANDIDATE"
        and row.commercial_truth_state == "UNTESTED"
        and row.relation_state == "ANALOGICAL_CANDIDATE"
        and row.market_demand_claimed is False
        and row.capability_created is False
        and row.authority_created is False
        and row.authority_widened is False
        and row.external_effects is False
        and row.execution_performed is False
        and row.authority_ceiling == "controlled_artifact_only"
        for row in candidates
    )
    domain_coverage_ratio = len(covered_domains) / len(eligible) if eligible else 0.0
    registry_digest = digest_payload([row.candidate_digest for row in candidates])
    passed = (
        len(registry.incarnations) == LEGACY_PORTFOLIO_COUNT
        and len(templates) >= 20
        and len(candidates) >= 500
        and len(candidates) > LEGACY_PORTFOLIO_COUNT
        and len(novel) > LEGACY_PORTFOLIO_COUNT
        and len(gap_bearing) > 0
        and state_counts["COMPOSABLE_CANDIDATE"] > 0
        and len(covered_domains) == len(eligible)
        and domain_coverage_ratio == 1.0
        and held_truth
    )
    return {
        "schema": "dio.atlas.derived_portfolio_surface_receipt.v1",
        "phase": "M4-0B",
        "acceptance": ATLAS_SURFACE_TOKEN if passed else ATLAS_SURFACE_BLOCKED,
        "passed": passed,
        "legacy_portfolio_incarnation_count": len(registry.incarnations),
        "legacy_portfolio_preserved_exactly": len(registry.incarnations) == LEGACY_PORTFOLIO_COUNT,
        "job_morphology_template_count": len(templates),
        "eligible_domain_node_count": len(eligible),
        "covered_domain_node_count": len(covered_domains),
        "domain_coverage_ratio": round(domain_coverage_ratio, 6),
        "derived_candidate_incarnation_count": len(candidates),
        "derived_candidate_count_exceeds_legacy_portfolio": len(candidates) > LEGACY_PORTFOLIO_COUNT,
        "candidate_to_legacy_ratio": round(len(candidates) / LEGACY_PORTFOLIO_COUNT, 3),
        "novel_candidate_incarnation_count": len(novel),
        "legacy_analogy_candidate_count": len(legacy_overlap),
        "gap_bearing_candidate_count": len(gap_bearing),
        "candidate_state_counts": dict(sorted(state_counts.items())),
        "mechanical_verdict_counts": dict(sorted(verdict_counts.items())),
        "candidate_family_counts": dict(sorted(family_counts.items())),
        "candidate_template_counts": dict(sorted(template_counts.items())),
        "capability_cost_counts": dict(sorted(cost_counts.items())),
        "candidate_registry_digest": registry_digest,
        "capability_cost_first_class": True,
        "capability_cost_basis": "ATLAS_PLANNING_ESTIMATE_NOT_OBSERVED_COST",
        "every_candidate_held_unproved": held_truth,
        "legacy_portfolio_is_generated_candidate_universe": False,
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "direct_learning_to_execution": False,
        "m4_final_verified": False,
    }


def negative_learning_surface_pivot_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    surface = candidate_surface_receipt(root)

    from commercial_metabolism.learning import phase8_projection_adaptation_receipt

    parent = phase8_projection_adaptation_receipt(root)
    pivot = rank_candidate_incarnations_from_negative_learning(
        root,
        m2_learning_receipt=parent,
        source_task_id="T000",
        top_k=25,
        max_per_family=3,
        max_per_template=5,
    )
    selected = pivot["candidates"]
    selected_states = Counter(row["candidate_state"] for row in selected)
    selected_families = sorted({row["domain_family"] for row in selected})
    selected_templates = sorted({row["template_id"] for row in selected})
    selected_domains = sorted({row["domain_id"] for row in selected})
    all_held = all(row["relation_state"] == "ANALOGICAL_CANDIDATE" for row in selected)
    passed = (
        surface.get("passed") is True
        and parent.get("passed") is True
        and parent.get("acceptance") == "DIO_M2_PROJECTION_ADAPTATION_READY"
        and parent.get("negative_learning_context_bound") is True
        and pivot.get("candidate_registry_count", 0) == surface.get("derived_candidate_incarnation_count")
        and pivot.get("candidate_registry_count", 0) >= 500
        and pivot.get("selected_candidate_count") == 25
        and len(selected_families) >= 8
        and len(selected_templates) >= 4
        and len(selected_domains) >= 8
        and pivot.get("source_domain_excluded") is True
        and all_held
        and pivot.get("market_demand_claimed") is False
        and pivot.get("capability_created") is False
        and pivot.get("authority_created") is False
        and pivot.get("authority_widened") is False
        and pivot.get("external_effects") is False
        and pivot.get("execution_performed") is False
        and pivot.get("direct_learning_to_execution") is False
    )
    return {
        "schema": "dio.atlas.vast_negative_learning_pivot_receipt.v1",
        "phase": "M4-0P",
        "acceptance": ATLAS_SURFACE_PIVOT_TOKEN if passed else ATLAS_SURFACE_PIVOT_BLOCKED,
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "negative_learning_context_bound": parent.get("negative_learning_context_bound") is True,
        "legacy_portfolio_incarnation_count": surface.get("legacy_portfolio_incarnation_count"),
        "derived_candidate_incarnation_count": surface.get("derived_candidate_incarnation_count"),
        "novel_candidate_incarnation_count": surface.get("novel_candidate_incarnation_count"),
        "candidate_to_legacy_ratio": surface.get("candidate_to_legacy_ratio"),
        "domain_coverage_ratio": surface.get("domain_coverage_ratio"),
        "selected_candidate_count": len(selected),
        "selected_domain_count": len(selected_domains),
        "selected_domain_family_count": len(selected_families),
        "selected_domain_families": selected_families,
        "selected_template_count": len(selected_templates),
        "selected_templates": selected_templates,
        "selected_candidate_state_counts": dict(sorted(selected_states.items())),
        "pivot_registry_digest": pivot.get("pivot_registry_digest"),
        "top_pivot_candidates": selected,
        "all_selected_candidates_held_analogical": all_held,
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "direct_learning_to_execution": False,
        "m4_final_verified": False,
    }


__all__ = [
    "ATLAS_SURFACE_BLOCKED",
    "ATLAS_SURFACE_PIVOT_BLOCKED",
    "ATLAS_SURFACE_PIVOT_TOKEN",
    "ATLAS_SURFACE_TOKEN",
    "candidate_surface_receipt",
    "negative_learning_surface_pivot_receipt",
]
