"""DIO ATLAS analogical resolver and held pivot-hypothesis compiler.

The resolver reasons over work morphology. It never turns taxonomy membership or
similarity into capability truth. Mechanical coverage is computed only from the
M1 execution-corroborated capability signatures that bind back to current
MetamorphicUnit identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from metamorphic.contracts import digest_payload, require_digest

from .registry import AtlasRegistry, AtlasRegistryError


ATLAS_PIVOT_TOKEN = "DIO_ATLAS_ANALOGICAL_PIVOT_FOUNDATION_READY"
ATLAS_PIVOT_BLOCKED_TOKEN = "DIO_ATLAS_ANALOGICAL_PIVOT_FOUNDATION_BLOCKED"


class AtlasPivotError(RuntimeError):
    pass


def _split(value: str | None) -> frozenset[str]:
    return frozenset(item.strip() for item in str(value or "").split("|") if item.strip())


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _artifact_tokens(value: str | None) -> frozenset[str]:
    raw = str(value or "").replace(";", "|").replace(",", "|")
    return frozenset(item.strip().casefold() for item in raw.split("|") if item.strip())


@dataclass(frozen=True, slots=True)
class AnalogicalResolution:
    task_id: str
    domain_id: str
    task_name: str
    verdict: str
    required_work_pattern_ids: tuple[str, ...]
    required_primitive_ids: tuple[str, ...]
    covered_primitive_ids: tuple[str, ...]
    missing_primitive_ids: tuple[str, ...]
    required_specialized_capabilities: tuple[str, ...]
    satisfied_specialized_capabilities: tuple[str, ...]
    missing_specialized_capabilities: tuple[str, ...]
    primitive_coverage: float
    authority_ceiling: str
    external_effect_intent: str
    analogy_state: str = "ANALOGICAL_CANDIDATE"
    capability_created: bool = False
    authority_created: bool = False
    authority_widened: bool = False
    external_effects: bool = False
    execution_performed: bool = False

    @property
    def resolution_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dio.atlas.analogical_resolution.v1",
            "task_id": self.task_id,
            "domain_id": self.domain_id,
            "task_name": self.task_name,
            "verdict": self.verdict,
            "required_work_pattern_ids": list(self.required_work_pattern_ids),
            "required_primitive_ids": list(self.required_primitive_ids),
            "covered_primitive_ids": list(self.covered_primitive_ids),
            "missing_primitive_ids": list(self.missing_primitive_ids),
            "required_specialized_capabilities": list(self.required_specialized_capabilities),
            "satisfied_specialized_capabilities": list(self.satisfied_specialized_capabilities),
            "missing_specialized_capabilities": list(self.missing_specialized_capabilities),
            "primitive_coverage": self.primitive_coverage,
            "authority_ceiling": self.authority_ceiling,
            "external_effect_intent": self.external_effect_intent,
            "analogy_state": self.analogy_state,
            "capability_created": self.capability_created,
            "authority_created": self.authority_created,
            "authority_widened": self.authority_widened,
            "external_effects": self.external_effects,
            "execution_performed": self.execution_performed,
            "resolution_digest": self.resolution_digest,
        }


@dataclass(frozen=True, slots=True)
class PivotCandidate:
    target_task_id: str
    target_domain_id: str
    target_task_name: str
    source_task_id: str
    morphology_similarity: float
    primitive_similarity: float
    work_pattern_similarity: float
    artifact_similarity: float
    verdict: str
    missing_primitive_ids: tuple[str, ...]
    missing_specialized_capabilities: tuple[str, ...]
    relation_state: str = "ANALOGICAL_CANDIDATE"

    @property
    def candidate_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_task_id": self.target_task_id,
            "target_domain_id": self.target_domain_id,
            "target_task_name": self.target_task_name,
            "source_task_id": self.source_task_id,
            "morphology_similarity": self.morphology_similarity,
            "primitive_similarity": self.primitive_similarity,
            "work_pattern_similarity": self.work_pattern_similarity,
            "artifact_similarity": self.artifact_similarity,
            "verdict": self.verdict,
            "missing_primitive_ids": list(self.missing_primitive_ids),
            "missing_specialized_capabilities": list(self.missing_specialized_capabilities),
            "relation_state": self.relation_state,
            "candidate_digest": self.candidate_digest,
        }


def resolve_task(registry: AtlasRegistry, task_id: str) -> AnalogicalResolution:
    row = registry.task(task_id)
    required_primitives = _split(row.get("required_primitive_ids"))
    verified_primitives = registry.verified_primitive_ids
    covered = required_primitives & verified_primitives
    missing = required_primitives - verified_primitives
    required_specialized = _split(row.get("required_specialized_capabilities"))
    satisfied_specialized = required_specialized & registry.capability_ids
    missing_specialized = required_specialized - registry.capability_ids
    coverage = len(covered) / len(required_primitives) if required_primitives else 0.0
    external_intent = str(row.get("external_effect_intent") or "NONE")

    if not missing and not missing_specialized and external_intent == "NONE":
        verdict = "COMPOSABLE"
    elif external_intent != "NONE" and missing_specialized:
        verdict = "UNSUPPORTED"
    elif coverage >= 0.45:
        verdict = "PARTIALLY_COMPOSABLE"
    else:
        verdict = "UNSUPPORTED"

    return AnalogicalResolution(
        task_id=row["task_id"],
        domain_id=row["domain_id"],
        task_name=row["task_name"],
        verdict=verdict,
        required_work_pattern_ids=tuple(sorted(_split(row.get("required_work_pattern_ids")))),
        required_primitive_ids=tuple(sorted(required_primitives)),
        covered_primitive_ids=tuple(sorted(covered)),
        missing_primitive_ids=tuple(sorted(missing)),
        required_specialized_capabilities=tuple(sorted(required_specialized)),
        satisfied_specialized_capabilities=tuple(sorted(satisfied_specialized)),
        missing_specialized_capabilities=tuple(sorted(missing_specialized)),
        primitive_coverage=round(coverage, 6),
        authority_ceiling=str(row.get("authority_ceiling") or ""),
        external_effect_intent=external_intent,
    )


def evaluate_pivot_gauntlet(registry: AtlasRegistry) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    passed = 0
    for task in registry.pivot_tasks:
        resolution = resolve_task(registry, task["task_id"])
        expected = str(task.get("expected_foundation_verdict") or "")
        match = resolution.verdict == expected
        passed += int(match)
        rows.append(
            {
                "task_id": task["task_id"],
                "domain_id": task["domain_id"],
                "task_name": task["task_name"],
                "expected": expected,
                "actual": resolution.verdict,
                "matched": match,
                "primitive_coverage": resolution.primitive_coverage,
                "missing_primitive_ids": list(resolution.missing_primitive_ids),
                "missing_specialized_capabilities": list(resolution.missing_specialized_capabilities),
                "resolution_digest": resolution.resolution_digest,
            }
        )
    return {
        "case_count": len(rows),
        "passed_case_count": passed,
        "all_cases_passed": passed == len(rows),
        "cases": rows,
    }


def pivot_candidates(
    registry: AtlasRegistry,
    *,
    source_task_id: str,
    excluded_domain_ids: Sequence[str] = (),
    top_k: int = 10,
) -> tuple[PivotCandidate, ...]:
    if top_k <= 0:
        raise AtlasPivotError("top_k must be positive")
    source = registry.task(source_task_id)
    source_primitives = _split(source.get("required_primitive_ids"))
    source_patterns = _split(source.get("required_work_pattern_ids"))
    source_artifacts = _artifact_tokens(source.get("artifact_classes"))
    blocked_domains = {str(value) for value in excluded_domain_ids}
    candidates: list[PivotCandidate] = []

    for target in registry.pivot_tasks:
        if target["task_id"] == source_task_id:
            continue
        if target["domain_id"] in blocked_domains:
            continue
        target_primitives = _split(target.get("required_primitive_ids"))
        target_patterns = _split(target.get("required_work_pattern_ids"))
        target_artifacts = _artifact_tokens(target.get("artifact_classes"))
        primitive_similarity = _jaccard(source_primitives, target_primitives)
        work_pattern_similarity = _jaccard(source_patterns, target_patterns)
        artifact_similarity = _jaccard(source_artifacts, target_artifacts)
        score = 0.75 * primitive_similarity + 0.15 * work_pattern_similarity + 0.10 * artifact_similarity
        # ATLAS intentionally does not add a same-domain or name-similarity bonus.
        resolution = resolve_task(registry, target["task_id"])
        candidates.append(
            PivotCandidate(
                target_task_id=target["task_id"],
                target_domain_id=target["domain_id"],
                target_task_name=target["task_name"],
                source_task_id=source_task_id,
                morphology_similarity=round(score, 6),
                primitive_similarity=round(primitive_similarity, 6),
                work_pattern_similarity=round(work_pattern_similarity, 6),
                artifact_similarity=round(artifact_similarity, 6),
                verdict=resolution.verdict,
                missing_primitive_ids=resolution.missing_primitive_ids,
                missing_specialized_capabilities=resolution.missing_specialized_capabilities,
            )
        )
    candidates.sort(key=lambda row: (-row.morphology_similarity, row.target_domain_id, row.target_task_id))
    return tuple(candidates[:top_k])


def compile_negative_learning_pivot(
    repo_root: str | Path,
    *,
    m2_learning_receipt: Mapping[str, Any],
    source_task_id: str = "T000",
    top_k: int = 10,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry = AtlasRegistry.load(root)
    if m2_learning_receipt.get("passed") is not True or m2_learning_receipt.get("acceptance") != "DIO_M2_PROJECTION_ADAPTATION_READY":
        raise AtlasPivotError("verified M2-8 negative-learning parent is required")
    if m2_learning_receipt.get("negative_learning_context_bound") is not True:
        raise AtlasPivotError("M2 negative learning is not context bound")
    context_digest = str(m2_learning_receipt.get("context_digest") or "")
    require_digest(context_digest, field_name="negative_learning_context_digest")
    negative_rows = m2_learning_receipt.get("negative_learning_records")
    if not isinstance(negative_rows, list) or not negative_rows:
        raise AtlasPivotError("M2 negative-learning records are required")
    record_ids = tuple(sorted(str(row.get("record_id") or "") for row in negative_rows if isinstance(row, Mapping)))
    if any(not value for value in record_ids):
        raise AtlasPivotError("M2 negative-learning record id missing")

    source = registry.task(source_task_id)
    excluded = (source["domain_id"],)
    candidates = pivot_candidates(
        registry,
        source_task_id=source_task_id,
        excluded_domain_ids=excluded,
        top_k=top_k,
    )
    if not candidates:
        raise AtlasPivotError("ATLAS produced no cross-domain pivot candidates")
    payload = {
        "schema": "dio.atlas.pivot_hypothesis.v1",
        "source_task_id": source_task_id,
        "source_domain_id": source["domain_id"],
        "negative_learning_context_digest": context_digest,
        "negative_learning_record_ids": list(record_ids),
        "source_domain_excluded_from_targets": True,
        "candidate_count": len(candidates),
        "candidates": [row.to_dict() for row in candidates],
        "candidate_relation_state": "ANALOGICAL_CANDIDATE",
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "execution_performed": False,
        "direct_learning_to_execution": False,
    }
    return {**payload, "pivot_hypothesis_digest": digest_payload(payload)}


def atlas_pivot_foundation_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    registry = AtlasRegistry.load(root)
    bindings = registry.bind_execution_signatures()
    gauntlet = evaluate_pivot_gauntlet(registry)

    from commercial_metabolism.learning import phase8_projection_adaptation_receipt

    parent = phase8_projection_adaptation_receipt(root)
    hypothesis = compile_negative_learning_pivot(
        root,
        m2_learning_receipt=parent,
        source_task_id="T000",
        top_k=10,
    )
    unknown = resolve_task(registry, "T014")
    medical = resolve_task(registry, "T016")
    aircraft = resolve_task(registry, "T018")
    exact_reference = resolve_task(registry, "T000")

    remote_candidates = {
        row["target_domain_id"]
        for row in hypothesis["candidates"]
        if row["target_domain_id"] != hypothesis["source_domain_id"]
    }
    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == "DIO_M2_PROJECTION_ADAPTATION_READY"
        and parent.get("negative_learning_context_bound") is True
        and len(bindings) == 4
        and gauntlet.get("all_cases_passed") is True
        and exact_reference.verdict == "COMPOSABLE"
        and unknown.verdict == "COMPOSABLE"
        and unknown.domain_id == "D1800"
        and medical.verdict != "COMPOSABLE"
        and "clinical_diagnosis" in medical.missing_specialized_capabilities
        and aircraft.verdict == "UNSUPPORTED"
        and "airworthiness_release" in aircraft.missing_specialized_capabilities
        and len(remote_candidates) >= 5
        and hypothesis.get("market_demand_claimed") is False
        and hypothesis.get("capability_created") is False
        and hypothesis.get("authority_created") is False
        and hypothesis.get("external_effects") is False
        and hypothesis.get("direct_learning_to_execution") is False
    )
    return {
        "phase": "M4-0A",
        "acceptance": ATLAS_PIVOT_TOKEN if passed else ATLAS_PIVOT_BLOCKED_TOKEN,
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": parent.get("reference_product"),
        "negative_learning_context_bound": parent.get("negative_learning_context_bound") is True,
        "active_negative_match_count": parent.get("active_negative_match_count"),
        "execution_signature_binding_count": len(bindings),
        "verified_capability_ids": sorted(bindings),
        "verified_primitive_count": len(registry.verified_primitive_ids),
        "pivot_gauntlet_case_count": gauntlet["case_count"],
        "pivot_gauntlet_passed_case_count": gauntlet["passed_case_count"],
        "pivot_gauntlet_all_cases_passed": gauntlet["all_cases_passed"],
        "unknown_domain_task_id": unknown.task_id,
        "unknown_domain_verdict": unknown.verdict,
        "unknown_domain_morphology_resolved": unknown.verdict == "COMPOSABLE",
        "medical_false_analogy_verdict": medical.verdict,
        "medical_specialized_capability_missing": "clinical_diagnosis" in medical.missing_specialized_capabilities,
        "aircraft_false_analogy_verdict": aircraft.verdict,
        "aircraft_specialized_capability_missing": "airworthiness_release" in aircraft.missing_specialized_capabilities,
        "pivot_hypothesis": hypothesis,
        "cross_domain_candidate_count": len(remote_candidates),
        "similarity_is_capability": False,
        "analogy_is_evidence": False,
        "domain_adjacency_is_market_demand": False,
        "task_match_is_execution_proof": False,
        "market_demand_claimed": False,
        "capability_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "direct_learning_to_execution": False,
        "execution_performed": False,
        "m4_final_verified": False,
    }


__all__ = [
    "ATLAS_PIVOT_BLOCKED_TOKEN",
    "ATLAS_PIVOT_TOKEN",
    "AnalogicalResolution",
    "AtlasPivotError",
    "PivotCandidate",
    "atlas_pivot_foundation_receipt",
    "compile_negative_learning_pivot",
    "evaluate_pivot_gauntlet",
    "pivot_candidates",
    "resolve_task",
]
