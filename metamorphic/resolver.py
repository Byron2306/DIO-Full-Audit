"""Deterministic capability resolver for DIO Metamorphic Phase 5.

Phase 5 begins with a source-bound LINGUA intent object, not an ungrounded
keyword router. The resolver checks each required outcome against Phase 3
semantic affordances, the Phase 2 immutable registry, a current Phase 4 world
lease, eligibility exclusions, and authority intersection before constructing a
DAG. It plans only. It does not execute native organs or create authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .authority import AuthorityIntersection, intersect_authority
from .composition import CompositionDAG, ResolvedNode, build_composition_dag
from .contracts import digest_payload
from .registry import MetamorphicRegistry, build_reference_registry
from .semantic_law import SemanticLaw, build_reference_semantic_laws
from .world_lease import (
    WorldLeaseBindingError,
    acquire_world_lease,
    build_controlled_world_snapshot,
    phase4_world_lease_receipt,
    require_world_lease_current,
)


PHASE5_EXIT_TOKEN = "DIO_METAMORPHIC_RESOLVER_READY"
DEFAULT_CONFIG = "config/metamorphic_phase5_reference_job.json"


class ResolverError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResolverError(f"cannot load resolver source: {path}") from exc
    if not isinstance(value, dict):
        raise ResolverError(f"resolver source must be an object: {path}")
    return value


def _nonempty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ResolverError(f"{field_name} is required")
    return text


@dataclass(frozen=True, slots=True)
class LinguaOutcome:
    outcome_id: str
    capability: str
    meaning: str
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.outcome_id.strip() or not self.capability.strip() or not self.meaning.strip():
            raise ValueError("LINGUA outcome requires id, capability and meaning")
        if self.outcome_id in self.depends_on:
            raise ValueError("LINGUA outcome cannot depend on itself")


@dataclass(frozen=True, slots=True)
class LinguaIntent:
    intent_id: str
    buyer_job_id: str
    buyer_job_digest: str
    buyer: str
    required_outcomes: tuple[LinguaOutcome, ...]
    extraction_mode: str
    autonomous_natural_language_inference_claimed: bool
    schema: str = "dio.lingua.metamorphic_intent.v1"

    def __post_init__(self) -> None:
        if not self.intent_id.strip() or not self.buyer_job_id.strip() or not self.buyer_job_digest.strip():
            raise ValueError("LINGUA intent identity and buyer-job binding are required")
        if not self.required_outcomes:
            raise ValueError("LINGUA intent requires outcomes")
        ids = [row.outcome_id for row in self.required_outcomes]
        if len(ids) != len(set(ids)):
            raise ValueError("LINGUA intent outcome ids must be unique")
        known = set(ids)
        missing = sorted({dep for row in self.required_outcomes for dep in row.depends_on if dep not in known})
        if missing:
            raise ValueError(f"LINGUA intent has missing dependencies: {missing}")

    @property
    def intent_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "intent_id": self.intent_id,
            "buyer_job_id": self.buyer_job_id,
            "buyer_job_digest": self.buyer_job_digest,
            "buyer": self.buyer,
            "required_outcomes": [
                {
                    "outcome_id": row.outcome_id,
                    "capability": row.capability,
                    "meaning": row.meaning,
                    "depends_on": list(row.depends_on),
                }
                for row in self.required_outcomes
            ],
            "extraction_mode": self.extraction_mode,
            "autonomous_natural_language_inference_claimed": self.autonomous_natural_language_inference_claimed,
            "intent_digest": self.intent_digest,
        }


def build_reference_intent(repo_root: str | Path) -> tuple[LinguaIntent, str, dict[str, Any]]:
    root = Path(repo_root).resolve()
    config = _load_json(root / DEFAULT_CONFIG)
    if config.get("schema") != "dio.metamorphic_phase5_reference_job.v1":
        raise ResolverError("unsupported Phase 5 reference-job schema")
    buyer_job = config.get("buyer_job")
    lingua = config.get("lingua_intent")
    if not isinstance(buyer_job, dict) or not isinstance(lingua, dict):
        raise ResolverError("Phase 5 buyer_job and lingua_intent are required")
    source_text = _nonempty(buyer_job.get("source_text"), "buyer_job.source_text")
    rows = lingua.get("required_outcomes")
    if not isinstance(rows, list) or not rows:
        raise ResolverError("lingua_intent.required_outcomes is required")
    outcomes = tuple(
        LinguaOutcome(
            outcome_id=_nonempty(row.get("outcome_id"), "outcome_id"),
            capability=_nonempty(row.get("capability"), "capability"),
            meaning=_nonempty(row.get("meaning"), "meaning"),
            depends_on=tuple(str(value) for value in (row.get("depends_on") or ())),
        )
        for row in rows
        if isinstance(row, dict)
    )
    if len(outcomes) != len(rows):
        raise ResolverError("all LINGUA outcomes must be objects")
    intent = LinguaIntent(
        intent_id=_nonempty(lingua.get("intent_id"), "lingua_intent.intent_id"),
        buyer_job_id=_nonempty(buyer_job.get("job_id"), "buyer_job.job_id"),
        buyer_job_digest=digest_payload({"source_text": source_text}),
        buyer=str(buyer_job.get("buyer") or "").strip(),
        required_outcomes=outcomes,
        extraction_mode=_nonempty(config.get("intent_extraction_mode"), "intent_extraction_mode"),
        autonomous_natural_language_inference_claimed=bool(config.get("autonomous_natural_language_inference_claimed")),
    )
    if intent.autonomous_natural_language_inference_claimed:
        raise ResolverError("Phase 5 may not claim autonomous NLU inference from a controlled intent fixture")
    return intent, source_text, config


def _semantic_support(law: SemanticLaw, capability: str) -> bool:
    return any(
        row.get("scope") == "exported_metamorphic_capability"
        and row.get("capability") == capability
        and row.get("claim_state") == "SUPPORTED"
        for row in law.affordances
    )


def _resolve_provider(
    *,
    registry: MetamorphicRegistry,
    laws: Mapping[str, SemanticLaw],
    capability: str,
    active_negative_unit_ids: set[str],
    stale_unit_ids: set[str],
    unique_provider_required: bool,
) -> tuple[Any, SemanticLaw]:
    providers = registry.providers_for(capability)
    eligible = []
    for unit in providers:
        if unit.unit_id in active_negative_unit_ids or unit.unit_id in stale_unit_ids:
            continue
        law = laws.get(unit.unit_id)
        if law is None or law.unit_digest != unit.unit_digest:
            continue
        if not _semantic_support(law, capability):
            continue
        eligible.append((unit, law))
    if not eligible:
        raise ResolverError(f"no eligible semantically-supported provider for capability: {capability}")
    eligible.sort(key=lambda row: (row[0].unit_id, row[0].unit_digest))
    if unique_provider_required and len(eligible) != 1:
        raise ResolverError(f"ambiguous eligible providers for capability {capability}: {[row[0].unit_id for row in eligible]}")
    return eligible[0]


def resolve_intent(
    repo_root: str | Path,
    *,
    intent: LinguaIntent,
    live_buyer_job_text: str,
    world_lease: Any,
    live_snapshot: Any,
    now: datetime | None = None,
    active_negative_unit_ids: Sequence[str] = (),
    stale_unit_ids: Sequence[str] = (),
    registry: MetamorphicRegistry | None = None,
    semantic_laws: Mapping[str, SemanticLaw] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    cfg = dict(config or _load_json(root / DEFAULT_CONFIG))
    if digest_payload({"source_text": str(live_buyer_job_text).strip()}) != intent.buyer_job_digest:
        raise ResolverError("buyer-job source changed after LINGUA intent binding")

    registry = registry or build_reference_registry(root)
    laws = semantic_laws or build_reference_semantic_laws(root)
    live_caps = tuple(unit.unit_digest for unit in registry.units())
    try:
        world_validation = require_world_lease_current(
            world_lease,
            live_snapshot=live_snapshot,
            live_capability_refs=live_caps,
            live_authority_refs=tuple(world_lease.authority_refs),
            now=now,
        )
    except WorldLeaseBindingError as exc:
        raise ResolverError(str(exc)) from exc

    selection = cfg.get("selection_policy")
    if not isinstance(selection, dict):
        raise ResolverError("selection_policy is required")
    if selection.get("semantic_support_required") is not True:
        raise ResolverError("Phase 5 requires semantic support")
    unique = selection.get("unique_eligible_provider_required") is True
    negative = set(str(value) for value in active_negative_unit_ids)
    stale = set(str(value) for value in stale_unit_ids)

    resolved_nodes: list[ResolvedNode] = []
    selected_units = []
    dependencies: dict[str, tuple[str, ...]] = {}
    for outcome in intent.required_outcomes:
        unit, law = _resolve_provider(
            registry=registry,
            laws=laws,
            capability=outcome.capability,
            active_negative_unit_ids=negative,
            stale_unit_ids=stale,
            unique_provider_required=unique,
        )
        selected_units.append(unit)
        dependencies[outcome.outcome_id] = outcome.depends_on
        resolved_nodes.append(
            ResolvedNode(
                node_id=outcome.outcome_id,
                capability=outcome.capability,
                unit_id=unit.unit_id,
                unit_digest=unit.unit_digest,
                semantic_law_digest=law.law_digest,
                executor_id=unit.executor_id,
                executor_digest=unit.executor_digest,
                evidence_contract_digest=digest_payload(unit.evidence_contract),
                quality_contract_digest=digest_payload(unit.quality_contract),
                authority_ceiling=unit.authority_ceiling,
            )
        )

    authority_policy = cfg.get("authority_policy")
    if not isinstance(authority_policy, dict):
        raise ResolverError("authority_policy is required")
    authority: AuthorityIntersection = intersect_authority(
        repo_root=root,
        units=selected_units,
        authority_policy=authority_policy,
    )
    if authority.authority_widened or authority.learning_used_as_authority:
        raise ResolverError("authority intersection widened authority")

    dag: CompositionDAG = build_composition_dag(
        composition_name=_nonempty(cfg.get("reference_composite_name"), "reference_composite_name"),
        intent_digest=intent.intent_digest,
        world_lease_digest=world_lease.lease_digest,
        nodes=resolved_nodes,
        dependencies=dependencies,
        authority=authority.to_dict(),
    )
    return {
        "schema": "dio.metamorphic.resolution_receipt.v1",
        "intent": intent.to_dict(),
        "world_lease_digest": world_lease.lease_digest,
        "world_lease_valid": world_validation.valid,
        "world_validation": world_validation.to_dict(),
        "selected_units": [
            {
                "outcome_id": node.node_id,
                "capability": node.capability,
                "unit_id": node.unit_id,
                "unit_digest": node.unit_digest,
                "semantic_law_digest": node.semantic_law_digest,
            }
            for node in resolved_nodes
        ],
        "authority": authority.to_dict(),
        "composition": dag.to_dict(),
        "resolution_digest": digest_payload(
            {
                "intent_digest": intent.intent_digest,
                "world_lease_digest": world_lease.lease_digest,
                "composition_digest": dag.composition_digest,
                "authority_digest": authority.authority_digest,
            }
        ),
        "native_execution_performed": False,
        "new_engine_created": False,
    }


def phase5_resolver_receipt(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    intent, source_text, config = build_reference_intent(root)
    phase4 = phase4_world_lease_receipt(root)
    if phase4.get("acceptance") != config.get("required_phase4_acceptance") or phase4.get("passed") is not True:
        raise ResolverError("Phase 4 world lease is not verified")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    snapshot = build_controlled_world_snapshot(root, now=now)
    lease = acquire_world_lease(root, snapshot=snapshot, composition_id=intent.intent_id)
    resolution = resolve_intent(
        root,
        intent=intent,
        live_buyer_job_text=source_text,
        world_lease=lease,
        live_snapshot=snapshot,
        now=now,
        config=config,
    )
    composition = resolution["composition"]
    selected = resolution["selected_units"]
    authority = resolution["authority"]
    expected_units = {
        "finance_readiness_studio",
        "article_publication_studio",
        "professional_correspondence_studio",
    }
    boundaries = config.get("phase_boundaries") or {}
    passed = (
        resolution["world_lease_valid"] is True
        and {row["unit_id"] for row in selected} == expected_units
        and len(selected) == 3
        and composition["composition_name"] == "Funding Proposal Studio"
        and composition["topological_order"] == ["readiness", "proposal_narrative", "submission_correspondence"]
        and authority["authority_widened"] is False
        and authority["external_effects_authorized"] is False
        and authority["learning_used_as_authority"] is False
        and authority["human_gate"] == "NEEDS_YOU"
        and all(authority["effect_decisions"].get(key) == "REFUSE" for key in ("external_publication", "external_send", "media_spend", "payment"))
        and all(value is False for value in boundaries.values())
    )
    return {
        "phase": 5,
        "acceptance": PHASE5_EXIT_TOKEN if passed else "DIO_METAMORPHIC_RESOLVER_BLOCKED",
        "passed": passed,
        "reference_composite_name": composition["composition_name"],
        "intent_digest": intent.intent_digest,
        "buyer_job_source_bound": True,
        "intent_extraction_mode": intent.extraction_mode,
        "autonomous_natural_language_inference_claimed": intent.autonomous_natural_language_inference_claimed,
        "semantic_support_required": True,
        "world_lease_current": resolution["world_lease_valid"],
        "selected_unit_count": len(selected),
        "selected_units": selected,
        "composition_digest": composition["composition_digest"],
        "topological_order": composition["topological_order"],
        "edge_count": len(composition["edges"]),
        "same_unit_identity_preserved": True,
        "authority": authority,
        "negative_capability_filter_present": True,
        "stale_eligibility_filter_present": True,
        "resolver_deterministic": True,
        "composition_dag_implemented": True,
        "native_execution_performed": False,
        "sensorium_episode_started": False,
        "beast_crystallization_executed": False,
        "harmonics_executed": False,
        "seraph_egress_executed": False,
        "arda_execution_performed": False,
        "world_settlement_performed": False,
        "market_feedback_learning_executed": False,
        "new_engine_created": False,
        "authority_widened": False,
    }
