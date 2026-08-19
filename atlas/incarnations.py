"""Derived candidate-incarnation registry for DIO ATLAS.

The historical 53-row DIO META portfolio remains an immutable crosswalk of what
was previously enumerated. This module derives a much larger *candidate* product
surface from ATLAS domain nodes × reusable job morphologies × execution-bound
capability signatures.

A generated candidate is not a product claim. It is a deterministic held
hypothesis describing where already-earned DIO mechanisms might fit, what is
missing, what the authority ceiling is, and how expensive the remaining
capability/validation work appears to be.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from metamorphic.contracts import digest_payload, require_digest

from .registry import ATLAS_CONFIG_ROOT, AtlasCapabilitySignature, AtlasRegistry, AtlasRegistryError


CANDIDATE_REGISTRY_TOKEN = "DIO_ATLAS_DERIVED_INCARNATION_REGISTRY_READY"
CANDIDATE_REGISTRY_BLOCKED = "DIO_ATLAS_DERIVED_INCARNATION_REGISTRY_BLOCKED"
NEGATIVE_PIVOT_REGISTRY_TOKEN = "DIO_ATLAS_NEGATIVE_LEARNING_PIVOT_REGISTRY_READY"
NEGATIVE_PIVOT_REGISTRY_BLOCKED = "DIO_ATLAS_NEGATIVE_LEARNING_PIVOT_REGISTRY_BLOCKED"
JOB_MORPHOLOGY_FILE = "dio_atlas_job_morphologies.csv"
LEGACY_PORTFOLIO_COUNT = 53


class AtlasIncarnationError(RuntimeError):
    pass


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split("|") if item.strip())


def _split_set(value: str | None) -> frozenset[str]:
    return frozenset(_split(value))


def _artifact_tokens(value: str | None) -> frozenset[str]:
    raw = str(value or "").replace(";", "|").replace(",", "|")
    return frozenset(item.strip().casefold() for item in raw.split("|") if item.strip())


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _truthy(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"true", "1", "yes"}


def _cost_category(score: float) -> str:
    if score < 1.5:
        return "LOW"
    if score < 2.5:
        return "LOW_MEDIUM"
    if score < 3.5:
        return "MEDIUM"
    if score < 4.5:
        return "HIGH"
    return "VERY_HIGH"


def _risk_uplift(safety_criticality: str) -> float:
    return {
        "LOW": 0.0,
        "MEDIUM": 0.25,
        "HIGH": 0.75,
        "VERY_HIGH": 1.25,
        "VARIABLE": 0.5,
    }.get(str(safety_criticality or "").upper(), 0.5)


def _read_rows(path: Path) -> tuple[dict[str, str], ...]:
    if not path.is_file():
        raise AtlasIncarnationError(f"ATLAS job morphology file missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = tuple(
            {str(key): str(value or "") for key, value in row.items()}
            for row in csv.DictReader(handle)
        )
    if not rows:
        raise AtlasIncarnationError(f"ATLAS job morphology file empty: {path}")
    return rows


@dataclass(frozen=True, slots=True)
class JobMorphologyTemplate:
    template_id: str
    template_name: str
    buyer_job: str
    applicable_domain_families: tuple[str, ...]
    required_work_pattern_ids: tuple[str, ...]
    required_primitive_ids: tuple[str, ...]
    required_specialized_capabilities: tuple[str, ...]
    input_artifact_classes: tuple[str, ...]
    output_artifact_class: str
    authority_ceiling: str
    external_effect_intent: str
    base_build_burden: float
    base_validation_burden: float
    commercial_shape: str
    notes: str

    def applies_to(self, domain_family: str) -> bool:
        return "ALL" in self.applicable_domain_families or domain_family in self.applicable_domain_families


@dataclass(frozen=True, slots=True)
class CandidateIncarnation:
    candidate_id: str
    domain_id: str
    domain_name: str
    domain_family: str
    domain_type: str
    template_id: str
    template_name: str
    buyer_job: str
    required_work_pattern_ids: tuple[str, ...]
    required_primitive_ids: tuple[str, ...]
    covered_primitive_ids: tuple[str, ...]
    missing_primitive_ids: tuple[str, ...]
    verified_capability_ids: tuple[str, ...]
    required_specialized_capabilities: tuple[str, ...]
    missing_specialized_capabilities: tuple[str, ...]
    primitive_coverage: float
    mechanical_verdict: str
    candidate_state: str
    input_artifact_classes: tuple[str, ...]
    output_artifact_class: str
    authority_ceiling: str
    professional_authority_required: bool
    safety_criticality: str
    external_effect_intent: str
    build_burden: float
    validation_burden: float
    capability_cost_score: float
    capability_cost: str
    capability_cost_basis: str
    domain_profile_state: str
    execution_truth_state: str
    commercial_truth_state: str
    relation_state: str
    legacy_analogy_count: int
    legacy_analogy_names: tuple[str, ...]
    market_demand_claimed: bool = False
    capability_created: bool = False
    authority_created: bool = False
    authority_widened: bool = False
    external_effects: bool = False
    execution_performed: bool = False

    @property
    def candidate_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "domain_family": self.domain_family,
            "domain_type": self.domain_type,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "buyer_job": self.buyer_job,
            "required_work_pattern_ids": list(self.required_work_pattern_ids),
            "required_primitive_ids": list(self.required_primitive_ids),
            "covered_primitive_ids": list(self.covered_primitive_ids),
            "missing_primitive_ids": list(self.missing_primitive_ids),
            "verified_capability_ids": list(self.verified_capability_ids),
            "required_specialized_capabilities": list(self.required_specialized_capabilities),
            "missing_specialized_capabilities": list(self.missing_specialized_capabilities),
            "primitive_coverage": self.primitive_coverage,
            "mechanical_verdict": self.mechanical_verdict,
            "candidate_state": self.candidate_state,
            "input_artifact_classes": list(self.input_artifact_classes),
            "output_artifact_class": self.output_artifact_class,
            "authority_ceiling": self.authority_ceiling,
            "professional_authority_required": self.professional_authority_required,
            "safety_criticality": self.safety_criticality,
            "external_effect_intent": self.external_effect_intent,
            "build_burden": self.build_burden,
            "validation_burden": self.validation_burden,
            "capability_cost_score": self.capability_cost_score,
            "capability_cost": self.capability_cost,
            "capability_cost_basis": self.capability_cost_basis,
            "domain_profile_state": self.domain_profile_state,
            "execution_truth_state": self.execution_truth_state,
            "commercial_truth_state": self.commercial_truth_state,
            "relation_state": self.relation_state,
            "legacy_analogy_count": self.legacy_analogy_count,
            "legacy_analogy_names": list(self.legacy_analogy_names),
            "market_demand_claimed": self.market_demand_claimed,
            "capability_created": self.capability_created,
            "authority_created": self.authority_created,
            "authority_widened": self.authority_widened,
            "external_effects": self.external_effects,
            "execution_performed": self.execution_performed,
        }


@dataclass(frozen=True, slots=True)
class RankedIncarnationPivot:
    candidate_id: str
    candidate_digest: str
    domain_id: str
    domain_name: str
    domain_family: str
    template_id: str
    template_name: str
    candidate_state: str
    mechanical_verdict: str
    morphology_similarity: float
    primitive_similarity: float
    work_pattern_similarity: float
    artifact_similarity: float
    primitive_coverage: float
    pivot_score: float
    capability_cost: str
    capability_cost_score: float
    missing_primitive_ids: tuple[str, ...]
    missing_specialized_capabilities: tuple[str, ...]
    relation_state: str = "ANALOGICAL_CANDIDATE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_digest": self.candidate_digest,
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "domain_family": self.domain_family,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "candidate_state": self.candidate_state,
            "mechanical_verdict": self.mechanical_verdict,
            "morphology_similarity": self.morphology_similarity,
            "primitive_similarity": self.primitive_similarity,
            "work_pattern_similarity": self.work_pattern_similarity,
            "artifact_similarity": self.artifact_similarity,
            "primitive_coverage": self.primitive_coverage,
            "pivot_score": self.pivot_score,
            "capability_cost": self.capability_cost,
            "capability_cost_score": self.capability_cost_score,
            "missing_primitive_ids": list(self.missing_primitive_ids),
            "missing_specialized_capabilities": list(self.missing_specialized_capabilities),
            "relation_state": self.relation_state,
        }


def load_job_morphologies(repo_root: str | Path, registry: AtlasRegistry | None = None) -> tuple[JobMorphologyTemplate, ...]:
    root = Path(repo_root).resolve()
    atlas = registry or AtlasRegistry.load(root)
    rows = _read_rows(root / ATLAS_CONFIG_ROOT / JOB_MORPHOLOGY_FILE)
    ids = [row.get("template_id", "") for row in rows]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise AtlasIncarnationError("ATLAS job morphology IDs must be unique and non-empty")
    templates: list[JobMorphologyTemplate] = []
    for row in rows:
        patterns = _split(row.get("required_work_pattern_ids"))
        primitives = _split(row.get("required_primitive_ids"))
        unknown_patterns = set(patterns) - atlas.work_pattern_ids
        unknown_primitives = set(primitives) - atlas.primitive_ids
        if unknown_patterns:
            raise AtlasIncarnationError(f"job morphology {row['template_id']} references unknown patterns {sorted(unknown_patterns)}")
        if unknown_primitives:
            raise AtlasIncarnationError(f"job morphology {row['template_id']} references unknown primitives {sorted(unknown_primitives)}")
        if row.get("authority_ceiling") != "controlled_artifact_only":
            raise AtlasIncarnationError(f"job morphology widened authority: {row['template_id']}")
        if row.get("external_effect_intent") != "NONE":
            raise AtlasIncarnationError(f"foundation job morphology must not require external effect: {row['template_id']}")
        templates.append(
            JobMorphologyTemplate(
                template_id=row["template_id"],
                template_name=row["template_name"],
                buyer_job=row["buyer_job"],
                applicable_domain_families=_split(row.get("applicable_domain_families")),
                required_work_pattern_ids=patterns,
                required_primitive_ids=primitives,
                required_specialized_capabilities=_split(row.get("required_specialized_capabilities")),
                input_artifact_classes=_split(row.get("input_artifact_classes")),
                output_artifact_class=row["output_artifact_class"],
                authority_ceiling=row["authority_ceiling"],
                external_effect_intent=row["external_effect_intent"],
                base_build_burden=float(row["base_build_burden"]),
                base_validation_burden=float(row["base_validation_burden"]),
                commercial_shape=row["commercial_shape"],
                notes=row.get("notes", ""),
            )
        )
    if len(templates) < 20:
        raise AtlasIncarnationError("ATLAS candidate compiler requires at least 20 reusable job morphologies")
    if sum(1 for template in templates if "ALL" in template.applicable_domain_families) < 2:
        raise AtlasIncarnationError("ATLAS requires at least two universal controlled-artifact morphologies")
    return tuple(templates)


def _minimal_capability_cover(
    signatures: Sequence[AtlasCapabilitySignature],
    required_primitives: frozenset[str],
) -> tuple[str, ...]:
    uncovered = set(required_primitives)
    selected: list[str] = []
    candidates = sorted(signatures, key=lambda row: row.capability_id)
    while uncovered:
        scored = sorted(
            (
                (len(uncovered & signature.primitive_set), signature.capability_id, signature)
                for signature in candidates
                if signature.capability_id not in selected
            ),
            key=lambda row: (-row[0], row[1]),
        )
        if not scored or scored[0][0] <= 0:
            break
        _coverage, capability_id, signature = scored[0]
        selected.append(capability_id)
        uncovered -= set(signature.primitive_ids)
    return tuple(selected)


def _legacy_analogies(
    registry: AtlasRegistry,
    *,
    domain_id: str,
    work_pattern_ids: frozenset[str],
) -> tuple[str, ...]:
    names: list[str] = []
    for row in registry.incarnations:
        domains = _split_set(row.get("atlas_domain_ids"))
        patterns = _split_set(row.get("canonical_work_pattern_ids")) | _split_set(row.get("candidate_work_pattern_ids"))
        if domain_id in domains and work_pattern_ids & patterns:
            names.append(row["incarnation"])
    return tuple(sorted(names))


def _candidate_id(domain_id: str, template_id: str) -> str:
    seed = {"domain_id": domain_id, "template_id": template_id, "schema": "dio.atlas.candidate_incarnation.v1"}
    suffix = digest_payload(seed).split(":", 1)[1][:16].upper()
    return f"ACI-{domain_id}-{template_id.replace('MORPH-', '')}-{suffix}"


def _candidate_state(verdict: str) -> str:
    return {
        "COMPOSABLE": "COMPOSABLE_CANDIDATE",
        "PARTIALLY_COMPOSABLE": "PARTIALLY_COMPOSABLE_CANDIDATE",
        "UNSUPPORTED": "CAPABILITY_GAP",
    }[verdict]


def _compile_one(
    registry: AtlasRegistry,
    domain: Mapping[str, str],
    template: JobMorphologyTemplate,
) -> CandidateIncarnation:
    required = frozenset(template.required_primitive_ids)
    covered = required & registry.verified_primitive_ids
    missing = required - registry.verified_primitive_ids
    required_specialized = frozenset(template.required_specialized_capabilities)
    missing_specialized = required_specialized - registry.capability_ids
    coverage = len(covered) / len(required) if required else 0.0

    if template.external_effect_intent != "NONE":
        verdict = "UNSUPPORTED"
    elif not missing and not missing_specialized:
        verdict = "COMPOSABLE"
    elif coverage >= 0.45:
        verdict = "PARTIALLY_COMPOSABLE"
    else:
        verdict = "UNSUPPORTED"

    selected_capabilities = _minimal_capability_cover(registry.signatures, required)
    professional = _truthy(domain.get("professional_authority_required"))
    build = min(
        5.0,
        template.base_build_burden
        + (1.0 - coverage) * 1.5
        + min(1.0, 0.25 * len(missing_specialized)),
    )
    validation = min(
        5.0,
        template.base_validation_burden
        + _risk_uplift(domain.get("safety_criticality", ""))
        + (0.5 if professional else 0.0)
        + min(0.75, 0.15 * len(missing_specialized)),
    )
    build = round(build, 3)
    validation = round(validation, 3)
    cost_score = round((build + validation) / 2.0, 3)
    patterns = frozenset(template.required_work_pattern_ids)
    legacy = _legacy_analogies(registry, domain_id=domain["domain_id"], work_pattern_ids=patterns)

    return CandidateIncarnation(
        candidate_id=_candidate_id(domain["domain_id"], template.template_id),
        domain_id=domain["domain_id"],
        domain_name=domain["domain_name"],
        domain_family=domain["domain_family"],
        domain_type=domain["domain_type"],
        template_id=template.template_id,
        template_name=template.template_name,
        buyer_job=template.buyer_job,
        required_work_pattern_ids=tuple(sorted(template.required_work_pattern_ids)),
        required_primitive_ids=tuple(sorted(required)),
        covered_primitive_ids=tuple(sorted(covered)),
        missing_primitive_ids=tuple(sorted(missing)),
        verified_capability_ids=selected_capabilities,
        required_specialized_capabilities=tuple(sorted(required_specialized)),
        missing_specialized_capabilities=tuple(sorted(missing_specialized)),
        primitive_coverage=round(coverage, 6),
        mechanical_verdict=verdict,
        candidate_state=_candidate_state(verdict),
        input_artifact_classes=template.input_artifact_classes,
        output_artifact_class=template.output_artifact_class,
        authority_ceiling=template.authority_ceiling,
        professional_authority_required=professional,
        safety_criticality=domain.get("safety_criticality", "VARIABLE"),
        external_effect_intent=template.external_effect_intent,
        build_burden=build,
        validation_burden=validation,
        capability_cost_score=cost_score,
        capability_cost=_cost_category(cost_score),
        capability_cost_basis="ATLAS_PLANNING_ESTIMATE_NOT_OBSERVED_COST",
        domain_profile_state="SOURCE_REFERENCED_NOT_EXECUTION_CORROBORATED",
        execution_truth_state="UNPROVED_CANDIDATE",
        commercial_truth_state="UNTESTED",
        relation_state="ANALOGICAL_CANDIDATE",
        legacy_analogy_count=len(legacy),
        legacy_analogy_names=legacy,
    )


def eligible_domain_nodes(registry: AtlasRegistry) -> tuple[dict[str, str], ...]:
    return tuple(
        row
        for row in registry.domains
        if row.get("domain_type") != "ROOT" and row.get("atlas_status") != "FEDERATION_ROOT"
    )


def compile_candidate_incarnations(
    repo_root: str | Path,
    *,
    registry: AtlasRegistry | None = None,
) -> tuple[CandidateIncarnation, ...]:
    root = Path(repo_root).resolve()
    atlas = registry or AtlasRegistry.load(root)
    templates = load_job_morphologies(root, atlas)
    candidates: list[CandidateIncarnation] = []
    for domain in eligible_domain_nodes(atlas):
        family = domain["domain_family"]
        applicable = [template for template in templates if template.applies_to(family)]
        if not applicable:
            raise AtlasIncarnationError(f"ATLAS domain has no applicable job morphology: {domain['domain_id']}")
        for template in applicable:
            candidates.append(_compile_one(atlas, domain, template))
    candidates.sort(key=lambda row: (row.domain_id, row.template_id, row.candidate_id))
    ids = [row.candidate_id for row in candidates]
    digests = [row.candidate_digest for row in candidates]
    if len(ids) != len(set(ids)):
        raise AtlasIncarnationError("derived ATLAS candidate IDs are not unique")
    if len(digests) != len(set(digests)):
        raise AtlasIncarnationError("derived ATLAS candidate digests are not unique")
    return tuple(candidates)


def candidate_registry_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry = AtlasRegistry.load(root)
    templates = load_job_morphologies(root, registry)
    candidates = compile_candidate_incarnations(root, registry=registry)
    eligible = eligible_domain_nodes(registry)
    covered_domains = {row.domain_id for row in candidates}
    state_counts = {
        state: sum(1 for row in candidates if row.candidate_state == state)
        for state in ("COMPOSABLE_CANDIDATE", "PARTIALLY_COMPOSABLE_CANDIDATE", "CAPABILITY_GAP")
    }
    family_counts = {
        family: sum(1 for row in candidates if row.domain_family == family)
        for family in sorted({row.domain_family for row in candidates})
    }
    template_counts = {
        template.template_id: sum(1 for row in candidates if row.template_id == template.template_id)
        for template in templates
    }
    novel = [row for row in candidates if row.legacy_analogy_count == 0]
    legacy_overlap = [row for row in candidates if row.legacy_analogy_count > 0]
    candidate_digest = digest_payload([row.candidate_digest for row in candidates])
    coverage_ratio = len(covered_domains) / len(eligible) if eligible else 0.0
    all_held = all(
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
    passed = (
        len(registry.incarnations) == LEGACY_PORTFOLIO_COUNT
        and len(templates) >= 20
        and len(candidates) >= 500
        and len(candidates) > LEGACY_PORTFOLIO_COUNT
        and len(novel) > LEGACY_PORTFOLIO_COUNT
        and len(covered_domains) == len(eligible)
        and coverage_ratio == 1.0
        and state_counts["COMPOSABLE_CANDIDATE"] > 0
        and state_counts["PARTIALLY_COMPOSABLE_CANDIDATE"] > 0
        and state_counts["CAPABILITY_GAP"] > 0
        and all_held
    )
    return {
        "schema": "dio.atlas.derived_candidate_registry_receipt.v1",
        "phase": "M4-0B",
        "acceptance": CANDIDATE_REGISTRY_TOKEN if passed else CANDIDATE_REGISTRY_BLOCKED,
        "passed": passed,
        "legacy_portfolio_incarnation_count": len(registry.incarnations),
        "legacy_portfolio_preserved_exactly": len(registry.incarnations) == LEGACY_PORTFOLIO_COUNT,
        "job_morphology_template_count": len(templates),
        "eligible_domain_node_count": len(eligible),
        "covered_domain_node_count": len(covered_domains),
        "domain_coverage_ratio": round(coverage_ratio, 6),
        "derived_candidate_incarnation_count": len(candidates),
        "derived_candidate_count_exceeds_legacy_portfolio": len(candidates) > LEGACY_PORTFOLIO_COUNT,
        "novel_candidate_incarnation_count": len(novel),
        "legacy_analogy_candidate_count": len(legacy_overlap),
        "candidate_state_counts": state_counts,
        "candidate_family_counts": family_counts,
        "candidate_template_counts": template_counts,
        "candidate_registry_digest": candidate_digest,
        "capability_cost_first_class": True,
        "capability_cost_basis": "ATLAS_PLANNING_ESTIMATE_NOT_OBSERVED_COST",
        "every_candidate_held_unproved": all_held,
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "direct_learning_to_execution": False,
        "m4_final_verified": False,
    }


def _pivot_rank_rows(
    registry: AtlasRegistry,
    candidates: Sequence[CandidateIncarnation],
    *,
    source_task_id: str,
) -> list[RankedIncarnationPivot]:
    source = registry.task(source_task_id)
    source_primitives = _split_set(source.get("required_primitive_ids"))
    source_patterns = _split_set(source.get("required_work_pattern_ids"))
    source_artifacts = _artifact_tokens(source.get("artifact_classes"))
    source_domain = source["domain_id"]
    ranked: list[RankedIncarnationPivot] = []
    for candidate in candidates:
        if candidate.domain_id == source_domain:
            continue
        primitive_similarity = _jaccard(source_primitives, frozenset(candidate.required_primitive_ids))
        work_pattern_similarity = _jaccard(source_patterns, frozenset(candidate.required_work_pattern_ids))
        artifact_similarity = _jaccard(source_artifacts, frozenset(item.casefold() for item in candidate.input_artifact_classes))
        morphology = 0.75 * primitive_similarity + 0.15 * work_pattern_similarity + 0.10 * artifact_similarity
        specialized_penalty = 0.90 if candidate.missing_specialized_capabilities else 1.0
        verdict_factor = {
            "COMPOSABLE": 1.0,
            "PARTIALLY_COMPOSABLE": 0.78,
            "UNSUPPORTED": 0.35,
        }[candidate.mechanical_verdict]
        fit_factor = 0.7 + 0.3 * candidate.primitive_coverage
        pivot_score = morphology * specialized_penalty * verdict_factor * fit_factor
        ranked.append(
            RankedIncarnationPivot(
                candidate_id=candidate.candidate_id,
                candidate_digest=candidate.candidate_digest,
                domain_id=candidate.domain_id,
                domain_name=candidate.domain_name,
                domain_family=candidate.domain_family,
                template_id=candidate.template_id,
                template_name=candidate.template_name,
                candidate_state=candidate.candidate_state,
                mechanical_verdict=candidate.mechanical_verdict,
                morphology_similarity=round(morphology, 6),
                primitive_similarity=round(primitive_similarity, 6),
                work_pattern_similarity=round(work_pattern_similarity, 6),
                artifact_similarity=round(artifact_similarity, 6),
                primitive_coverage=candidate.primitive_coverage,
                pivot_score=round(pivot_score, 6),
                capability_cost=candidate.capability_cost,
                capability_cost_score=candidate.capability_cost_score,
                missing_primitive_ids=candidate.missing_primitive_ids,
                missing_specialized_capabilities=candidate.missing_specialized_capabilities,
            )
        )
    ranked.sort(key=lambda row: (-row.pivot_score, row.domain_family, row.domain_id, row.template_id, row.candidate_id))
    return ranked


def rank_candidate_incarnations_from_negative_learning(
    repo_root: str | Path,
    *,
    m2_learning_receipt: Mapping[str, Any],
    source_task_id: str = "T000",
    top_k: int = 25,
    max_per_family: int = 3,
    max_per_template: int = 5,
) -> dict[str, Any]:
    if top_k <= 0 or max_per_family <= 0 or max_per_template <= 0:
        raise AtlasIncarnationError("pivot ranking limits must be positive")
    if m2_learning_receipt.get("passed") is not True or m2_learning_receipt.get("acceptance") != "DIO_M2_PROJECTION_ADAPTATION_READY":
        raise AtlasIncarnationError("verified M2-8 projection-adaptation receipt is required")
    if m2_learning_receipt.get("negative_learning_context_bound") is not True:
        raise AtlasIncarnationError("negative market learning must be context bound")
    context_digest = str(m2_learning_receipt.get("context_digest") or "")
    require_digest(context_digest, field_name="negative_learning_context_digest")
    negative_records = m2_learning_receipt.get("negative_learning_records")
    if not isinstance(negative_records, list) or not negative_records:
        raise AtlasIncarnationError("negative-learning records are required")
    record_ids = tuple(
        sorted(
            str(row.get("record_id") or "")
            for row in negative_records
            if isinstance(row, Mapping)
        )
    )
    if not record_ids or any(not value for value in record_ids):
        raise AtlasIncarnationError("negative-learning record identity is incomplete")

    root = Path(repo_root).resolve()
    registry = AtlasRegistry.load(root)
    candidates = compile_candidate_incarnations(root, registry=registry)
    ranked = _pivot_rank_rows(registry, candidates, source_task_id=source_task_id)
    selected: list[RankedIncarnationPivot] = []
    family_counts: dict[str, int] = {}
    template_counts: dict[str, int] = {}
    selected_ids: set[str] = set()
    for row in ranked:
        if len(selected) >= top_k:
            break
        if family_counts.get(row.domain_family, 0) >= max_per_family:
            continue
        if template_counts.get(row.template_id, 0) >= max_per_template:
            continue
        selected.append(row)
        selected_ids.add(row.candidate_id)
        family_counts[row.domain_family] = family_counts.get(row.domain_family, 0) + 1
        template_counts[row.template_id] = template_counts.get(row.template_id, 0) + 1
    if len(selected) < top_k:
        for row in ranked:
            if len(selected) >= top_k:
                break
            if row.candidate_id in selected_ids:
                continue
            selected.append(row)
            selected_ids.add(row.candidate_id)
    source = registry.task(source_task_id)
    payload = {
        "schema": "dio.atlas.negative_learning_candidate_registry_pivot.v1",
        "source_task_id": source_task_id,
        "source_domain_id": source["domain_id"],
        "negative_learning_context_digest": context_digest,
        "negative_learning_record_ids": list(record_ids),
        "candidate_registry_count": len(candidates),
        "ranked_candidate_count": len(ranked),
        "selected_candidate_count": len(selected),
        "selected_domain_family_count": len({row.domain_family for row in selected}),
        "selected_template_count": len({row.template_id for row in selected}),
        "source_domain_excluded": all(row.domain_id != source["domain_id"] for row in selected),
        "candidates": [row.to_dict() for row in selected],
        "relation_state": "ANALOGICAL_CANDIDATE",
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "direct_learning_to_execution": False,
    }
    return {**payload, "pivot_registry_digest": digest_payload(payload)}


def negative_learning_candidate_registry_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry_receipt = candidate_registry_receipt(root)
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
    passed = (
        registry_receipt.get("passed") is True
        and parent.get("passed") is True
        and parent.get("acceptance") == "DIO_M2_PROJECTION_ADAPTATION_READY"
        and parent.get("negative_learning_context_bound") is True
        and pivot.get("candidate_registry_count", 0) >= 500
        and pivot.get("selected_candidate_count") == 25
        and pivot.get("selected_domain_family_count", 0) >= 8
        and pivot.get("selected_template_count", 0) >= 4
        and pivot.get("source_domain_excluded") is True
        and all(row.get("relation_state") == "ANALOGICAL_CANDIDATE" for row in selected)
        and pivot.get("market_demand_claimed") is False
        and pivot.get("capability_created") is False
        and pivot.get("authority_created") is False
        and pivot.get("external_effects") is False
        and pivot.get("execution_performed") is False
        and pivot.get("direct_learning_to_execution") is False
    )
    return {
        "schema": "dio.atlas.negative_learning_candidate_registry_receipt.v1",
        "phase": "M4-0P",
        "acceptance": NEGATIVE_PIVOT_REGISTRY_TOKEN if passed else NEGATIVE_PIVOT_REGISTRY_BLOCKED,
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "negative_learning_context_bound": parent.get("negative_learning_context_bound") is True,
        "legacy_portfolio_incarnation_count": registry_receipt.get("legacy_portfolio_incarnation_count"),
        "derived_candidate_incarnation_count": registry_receipt.get("derived_candidate_incarnation_count"),
        "novel_candidate_incarnation_count": registry_receipt.get("novel_candidate_incarnation_count"),
        "candidate_state_counts": registry_receipt.get("candidate_state_counts"),
        "domain_coverage_ratio": registry_receipt.get("domain_coverage_ratio"),
        "selected_candidate_count": pivot.get("selected_candidate_count"),
        "selected_domain_family_count": pivot.get("selected_domain_family_count"),
        "selected_template_count": pivot.get("selected_template_count"),
        "pivot_registry_digest": pivot.get("pivot_registry_digest"),
        "top_pivot_candidates": selected,
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "direct_learning_to_execution": False,
        "m4_final_verified": False,
    }


CSV_FIELDS = (
    "candidate_id",
    "candidate_digest",
    "domain_id",
    "domain_name",
    "domain_family",
    "domain_type",
    "template_id",
    "template_name",
    "buyer_job",
    "candidate_state",
    "mechanical_verdict",
    "primitive_coverage",
    "required_work_pattern_ids",
    "required_primitive_ids",
    "covered_primitive_ids",
    "missing_primitive_ids",
    "verified_capability_ids",
    "required_specialized_capabilities",
    "missing_specialized_capabilities",
    "input_artifact_classes",
    "output_artifact_class",
    "authority_ceiling",
    "professional_authority_required",
    "safety_criticality",
    "external_effect_intent",
    "build_burden",
    "validation_burden",
    "capability_cost_score",
    "capability_cost",
    "capability_cost_basis",
    "domain_profile_state",
    "execution_truth_state",
    "commercial_truth_state",
    "relation_state",
    "legacy_analogy_count",
    "legacy_analogy_names",
    "market_demand_claimed",
    "capability_created",
    "authority_created",
    "authority_widened",
    "external_effects",
    "execution_performed",
)


def materialize_candidate_registry_csv(
    repo_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    candidates = compile_candidate_incarnations(root)
    target = Path(output_path)
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            row = candidate.to_dict()
            flat = dict(row)
            for key in (
                "required_work_pattern_ids",
                "required_primitive_ids",
                "covered_primitive_ids",
                "missing_primitive_ids",
                "verified_capability_ids",
                "required_specialized_capabilities",
                "missing_specialized_capabilities",
                "input_artifact_classes",
                "legacy_analogy_names",
            ):
                flat[key] = "|".join(str(value) for value in row[key])
            writer.writerow({field: flat[field] for field in CSV_FIELDS})
    return {
        "schema": "dio.atlas.candidate_registry_materialization_receipt.v1",
        "output_path": str(target),
        "candidate_count": len(candidates),
        "output_exists": target.is_file(),
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "external_effects": False,
    }


__all__ = [
    "CANDIDATE_REGISTRY_BLOCKED",
    "CANDIDATE_REGISTRY_TOKEN",
    "CSV_FIELDS",
    "JOB_MORPHOLOGY_FILE",
    "LEGACY_PORTFOLIO_COUNT",
    "NEGATIVE_PIVOT_REGISTRY_BLOCKED",
    "NEGATIVE_PIVOT_REGISTRY_TOKEN",
    "AtlasIncarnationError",
    "CandidateIncarnation",
    "JobMorphologyTemplate",
    "RankedIncarnationPivot",
    "candidate_registry_receipt",
    "compile_candidate_incarnations",
    "eligible_domain_nodes",
    "load_job_morphologies",
    "materialize_candidate_registry_csv",
    "negative_learning_candidate_registry_receipt",
    "rank_candidate_incarnations_from_negative_learning",
]
