"""M2 Phase 2 LINGUA commercial projection law.

This phase projects a verified product into buyer-facing commercial meaning without
turning proof gaps into marketing claims. It reuses the existing LINGUA semantic
lifecycle, binds every claim to an exact CommercialContext, and keeps release
and spend authority outside the projection layer.

The deterministic phrase guard is deliberately narrow. It checks configured
phrases only and does not claim autonomous natural-language claim inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from adapters.lingua.lifecycle import register_product_source
from metamorphic.contracts import digest_payload, require_digest
from metamorphic.crystallisation import PHASE9_EXIT_TOKEN, phase9_m1_receipt
from metamorphic.world_lease import phase4_world_lease_receipt
from products.funding_proposal_studio import build_funding_proposal_metamorphic_unit

from .contracts import CommercialContext, OfferLifecycle, OfferState, M2_PHASE1_EXIT_TOKEN, phase1_contract_receipt


M2_PHASE2_EXIT_TOKEN = "DIO_M2_LINGUA_COMMERCIAL_PROJECTION_READY"
DEFAULT_PROJECTION_CONFIG = "config/m2_phase2_commercial_projection.json"
PROJECTION_SCHEMA_FILE = "schemas/dio.commercial_projection.v1.json"


class CommercialProjectionError(RuntimeError):
    pass


class CommercialClaimState(str, Enum):
    SUPPORTED = "SUPPORTED"
    HELD_UNPROVED = "HELD_UNPROVED"
    REFUSE = "REFUSE"


@dataclass(frozen=True, slots=True)
class CommercialClaim:
    claim_id: str
    statement: str
    state: CommercialClaimState
    rule: str
    context_digest: str
    evidence_refs: tuple[str, ...] = ()
    schema: str = "dio.commercial_claim.v1"

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.statement.strip() or not self.rule.strip():
            raise ValueError("claim_id, statement and rule are required")
        require_digest(self.context_digest, field_name="context_digest")
        state = self.state if isinstance(self.state, CommercialClaimState) else CommercialClaimState(self.state)
        object.__setattr__(self, "state", state)
        if any(not isinstance(value, str) or not value.strip() for value in self.evidence_refs):
            raise ValueError("evidence_refs must contain non-empty strings")

    @property
    def allowed_in_buyer_copy(self) -> bool:
        return self.state == CommercialClaimState.SUPPORTED

    @property
    def claim_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "state": self.state.value,
            "rule": self.rule,
            "context_digest": self.context_digest,
            "evidence_refs": list(self.evidence_refs),
            "allowed_in_buyer_copy": self.allowed_in_buyer_copy,
        }


@dataclass(frozen=True, slots=True)
class CommercialProjection:
    projection_id: str
    product_id: str
    context_digest: str
    unit_digest: str
    offer_state_digest: str
    semantic_object_id: str
    lingua_source_document_hash: str
    claims: tuple[CommercialClaim, ...]
    claim_extraction_mode: str
    autonomous_natural_language_claim_inference_claimed: bool = False
    authority_created: bool = False
    external_effects: bool = False
    schema: str = "dio.commercial_projection.v1"

    def __post_init__(self) -> None:
        for field_name in ("projection_id", "product_id", "semantic_object_id", "claim_extraction_mode"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        for field_name in ("context_digest", "unit_digest", "offer_state_digest", "lingua_source_document_hash"):
            require_digest(getattr(self, field_name), field_name=field_name)
        if not self.claims:
            raise ValueError("projection requires claims")
        ids = [claim.claim_id for claim in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("projection claim ids must be unique")
        if any(claim.context_digest != self.context_digest for claim in self.claims):
            raise ValueError("all claims must bind the exact commercial context")
        if self.autonomous_natural_language_claim_inference_claimed:
            raise ValueError("M2-2 does not prove autonomous natural-language claim inference")
        if self.authority_created or self.external_effects:
            raise ValueError("commercial projection may not create authority or external effects")

    @property
    def projection_digest(self) -> str:
        return digest_payload(self)

    @property
    def supported_claims(self) -> tuple[CommercialClaim, ...]:
        return tuple(row for row in self.claims if row.state == CommercialClaimState.SUPPORTED)

    @property
    def held_claims(self) -> tuple[CommercialClaim, ...]:
        return tuple(row for row in self.claims if row.state == CommercialClaimState.HELD_UNPROVED)

    @property
    def refused_claims(self) -> tuple[CommercialClaim, ...]:
        return tuple(row for row in self.claims if row.state == CommercialClaimState.REFUSE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "projection_id": self.projection_id,
            "product_id": self.product_id,
            "context_digest": self.context_digest,
            "unit_digest": self.unit_digest,
            "offer_state_digest": self.offer_state_digest,
            "semantic_object_id": self.semantic_object_id,
            "lingua_source_document_hash": self.lingua_source_document_hash,
            "claims": [row.to_dict() for row in self.claims],
            "claim_extraction_mode": self.claim_extraction_mode,
            "autonomous_natural_language_claim_inference_claimed": self.autonomous_natural_language_claim_inference_claimed,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "projection_digest": self.projection_digest,
        }


def _load_config(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_PROJECTION_CONFIG
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialProjectionError(f"cannot load M2-2 projection config: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != "dio.m2.commercial_projection_config.v1":
        raise CommercialProjectionError("unsupported M2-2 projection config")
    return value


def build_reference_commercial_context(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> CommercialContext:
    root = Path(repo_root).resolve()
    config = _load_config(root)
    parent = phase1_contract_receipt(root)
    if parent.get("passed") is not True or parent.get("acceptance") != config.get("required_parent_acceptance"):
        raise CommercialProjectionError("M2-1 parent contracts are not verified")
    m1 = phase9_m1_receipt(root)
    if m1.get("passed") is not True or m1.get("acceptance") != config.get("required_m1_acceptance"):
        raise CommercialProjectionError("M1 parent is not verified")
    unit = build_funding_proposal_metamorphic_unit(root)
    if m1.get("composite_unit", {}).get("unit_digest") != unit.unit_digest:
        raise CommercialProjectionError("current Funding Proposal unit does not match verified M1 composite identity")
    world = phase4_world_lease_receipt(root)
    if world.get("passed") is not True or world.get("lease_current") is not True:
        raise CommercialProjectionError("current world lease proof is unavailable")

    ref = config.get("reference_context") or {}
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    period_seconds = int(ref.get("period_seconds") or 0)
    if period_seconds <= 0:
        raise CommercialProjectionError("reference context period_seconds must be positive")
    end = current + timedelta(seconds=period_seconds)
    market_state_digest = digest_payload({
        "schema": "dio.m2.market_state.reference.v1",
        "state": "UNOBSERVED_REFERENCE",
        "market_response_observed": False,
        "phase": "M2-2",
    })
    creative_profile_digest = digest_payload({
        "product_id": unit.unit_id,
        "projection": "controlled_reference",
        "buyer_projection": dict(unit.buyer_projection),
    })
    copy_profile_digest = digest_payload({
        "claim_extraction_mode": config.get("claim_extraction_mode"),
        "claims": config.get("claims") or [],
    })
    return CommercialContext(
        context_id=str(ref.get("context_id") or ""),
        product_id=unit.unit_id,
        metamorphic_unit_digest=unit.unit_digest,
        buyer_segment_id=str(ref.get("buyer_segment_id") or ""),
        jurisdiction=str(ref.get("jurisdiction") or ""),
        channel_id=str(ref.get("channel_id") or ""),
        offer_id=str(ref.get("offer_id") or ""),
        currency=str(ref.get("currency") or ""),
        price_minor=int(ref.get("price_minor") or 0),
        period_start=current.isoformat(),
        period_end=end.isoformat(),
        world_lease_digest=str(world["lease_digest"]),
        world_state_digest=str(world["snapshot_digest"]),
        market_state_digest=market_state_digest,
        creative_profile_digest=creative_profile_digest,
        copy_profile_digest=copy_profile_digest,
        source_refs=tuple(str(value) for value in (ref.get("source_refs") or [])),
    )


def _state_for_rule(
    rule: str,
    *,
    statement: str,
    m1: Mapping[str, Any],
    unit: Any,
) -> tuple[CommercialClaimState, tuple[str, ...]]:
    if rule == "unit_buyer_promise":
        expected = str(unit.buyer_projection.get("promise") or "")
        if statement != expected:
            raise CommercialProjectionError("configured buyer promise diverges from the current metamorphic unit")
        return CommercialClaimState.SUPPORTED, (unit.unit_digest,)
    if rule == "m1_composite_verified":
        passed = m1.get("passed") is True and m1.get("acceptance") == PHASE9_EXIT_TOKEN
        state = CommercialClaimState.SUPPORTED if passed else CommercialClaimState.HELD_UNPROVED
        return state, tuple(filter(None, (str(m1.get("composition_digest") or ""), unit.unit_digest)))
    if rule == "m1_settled_crystal":
        crystal = m1.get("beast_crystal") or {}
        passed = (
            m1.get("world_settlement_complete") is True
            and m1.get("beast_crystallization_executed") is True
            and crystal.get("crystal_chain_valid") is True
        )
        refs = tuple(filter(None, (str(m1.get("settlement_digest") or ""), str(crystal.get("crystal_block_hash") or ""))))
        return (CommercialClaimState.SUPPORTED if passed else CommercialClaimState.HELD_UNPROVED), refs
    if rule == "m1_same_identity":
        passed = m1.get("same_composite_identity_across_roles") is True and m1.get("composite_provider_reentry") is True
        return (CommercialClaimState.SUPPORTED if passed else CommercialClaimState.HELD_UNPROVED), (unit.unit_digest,)
    if rule == "m1_no_external_effects":
        passed = m1.get("external_effects") is False and m1.get("authority_widened") is False
        return (CommercialClaimState.SUPPORTED if passed else CommercialClaimState.HELD_UNPROVED), (unit.unit_digest,)
    if rule == "m1_content_dataflow":
        passed = m1.get("content_transform_dataflow_proved") is True
        return (CommercialClaimState.SUPPORTED if passed else CommercialClaimState.HELD_UNPROVED), (unit.unit_digest,)
    if rule in {
        "m2_market_demand",
        "m2_customer_acceptance",
        "m2_wtp",
        "m2_commercial_validation",
        "m2_repeatability",
        "m2_roi",
    }:
        return CommercialClaimState.HELD_UNPROVED, ()
    if rule in {
        "constitutional_guaranteed_outcome",
        "constitutional_external_submission",
        "constitutional_external_authority",
        "constitutional_success_authority",
    }:
        return CommercialClaimState.REFUSE, ()
    raise CommercialProjectionError(f"unsupported commercial claim rule: {rule}")


def build_commercial_projection(
    repo_root: str | Path,
    *,
    context: CommercialContext,
    work_root: str | Path,
) -> tuple[CommercialProjection, OfferState, dict[str, Any]]:
    root = Path(repo_root).resolve()
    config = _load_config(root)
    parent = phase1_contract_receipt(root)
    if parent.get("passed") is not True or parent.get("acceptance") != M2_PHASE1_EXIT_TOKEN:
        raise CommercialProjectionError("M2-1 parent contracts are not verified")
    m1 = phase9_m1_receipt(root)
    if m1.get("passed") is not True or m1.get("acceptance") != PHASE9_EXIT_TOKEN:
        raise CommercialProjectionError("verified M1 parent is required for commercial projection")
    unit = build_funding_proposal_metamorphic_unit(root)
    if context.product_id != unit.unit_id or context.metamorphic_unit_digest != unit.unit_digest:
        raise CommercialProjectionError("commercial context is not bound to the verified Funding Proposal unit")
    if m1.get("composite_unit", {}).get("unit_digest") != unit.unit_digest:
        raise CommercialProjectionError("M1 receipt and current Funding Proposal identity diverge")

    claim_specs = config.get("claims")
    if not isinstance(claim_specs, list) or not claim_specs:
        raise CommercialProjectionError("M2-2 requires configured claims")
    claims: list[CommercialClaim] = []
    for spec in claim_specs:
        if not isinstance(spec, dict):
            raise CommercialProjectionError("claim specification must be an object")
        claim_id = str(spec.get("id") or "").strip()
        statement = str(spec.get("statement") or "").strip()
        rule = str(spec.get("rule") or "").strip()
        state, evidence_refs = _state_for_rule(rule, statement=statement, m1=m1, unit=unit)
        claims.append(
            CommercialClaim(
                claim_id=claim_id,
                statement=statement,
                state=state,
                rule=rule,
                context_digest=context.context_digest,
                evidence_refs=evidence_refs,
            )
        )

    state_root = Path(work_root).resolve() / "lingua"
    semantic_object_id = f"M2P2-{context.context_digest.split(':', 1)[1][:20]}"
    source_rows = [
        {"unit_id": "TITLE", "unit_type": "title", "text": "Funding Proposal Studio"},
        {"unit_id": "PROMISE", "unit_type": "buyer_promise", "text": str(unit.buyer_projection["promise"])},
        {
            "unit_id": "PROOF_BOUNDARY",
            "unit_type": "proof_boundary",
            "text": (
                "Verified M1 proof covers governed composition, native execution, settlement, crystallisation and registry re-entry. "
                "Substantive content-transform dataflow remains unproved."
            ),
        },
        {
            "unit_id": "COMMERCIAL_BOUNDARY",
            "unit_type": "commercial_boundary",
            "text": (
                "M2-2 does not claim market demand, independent customer acceptance, willingness to pay, commercial validation, "
                "repeatability or ROI."
            ),
        },
        {
            "unit_id": "AUTHORITY_BOUNDARY",
            "unit_type": "authority_boundary",
            "text": (
                "Controlled artifact only. Publication, send, spend, payment, deploy and delivery authority remain separate."
            ),
        },
    ]
    semantic_object, registration = register_product_source(
        state_root=state_root,
        object_id=semantic_object_id,
        source_version="1.0.0",
        source_language="English",
        source_rows=source_rows,
        origin={
            "product": unit.unit_id,
            "artifact_type": "commercial_offer_projection",
            "artifact_id": context.offer_id,
            "audience": context.buyer_segment_id,
            "channel": context.channel_id,
            "privacy_domain": "controlled_reference",
        },
        domain="Governed commercial projection",
    )
    source_hash = str(semantic_object.get("source", {}).get("document_hash") or "")
    require_digest(source_hash, field_name="lingua_source_document_hash")

    offer = OfferState(
        offer_state_id=f"OFFSTATE-{context.context_digest.split(':', 1)[1][:16]}",
        offer_id=context.offer_id,
        product_id=context.product_id,
        context_digest=context.context_digest,
        version="1.0.0",
        lifecycle=OfferLifecycle.HELD,
        price_hypothesis_id=f"PRICE-{context.context_digest.split(':', 1)[1][:16]}",
        semantic_object_ref=semantic_object_id,
        authority_ceiling=unit.authority_ceiling,
        claim_refs=tuple(row.claim_digest for row in claims),
        evidence_refs=tuple(filter(None, (
            str(m1.get("settlement_digest") or ""),
            str((m1.get("beast_crystal") or {}).get("crystal_block_hash") or ""),
        ))),
        authority_created=False,
    )
    projection = CommercialProjection(
        projection_id=f"projection:{digest_payload({'context': context.context_digest, 'offer': offer.offer_state_digest}).split(':', 1)[1][:24]}",
        product_id=context.product_id,
        context_digest=context.context_digest,
        unit_digest=unit.unit_digest,
        offer_state_digest=offer.offer_state_digest,
        semantic_object_id=semantic_object_id,
        lingua_source_document_hash=source_hash,
        claims=tuple(claims),
        claim_extraction_mode=str(config.get("claim_extraction_mode") or ""),
        autonomous_natural_language_claim_inference_claimed=bool(
            config.get("autonomous_natural_language_claim_inference_claimed", False)
        ),
        authority_created=False,
        external_effects=False,
    )
    return projection, offer, registration


def evaluate_buyer_draft(
    repo_root: str | Path,
    *,
    projection: CommercialProjection,
    draft_text: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    config = _load_config(root)
    text = str(draft_text or "").casefold()
    claim_by_id = {row.claim_id: row for row in projection.claims}
    matched: list[dict[str, Any]] = []
    blocked: list[str] = []
    for spec in config.get("claims") or []:
        claim_id = str(spec.get("id") or "")
        claim = claim_by_id.get(claim_id)
        if claim is None:
            raise CommercialProjectionError(f"projection missing configured claim: {claim_id}")
        phrases = [str(value).casefold() for value in (spec.get("guard_phrases") or []) if str(value).strip()]
        hits = sorted({phrase for phrase in phrases if phrase in text})
        if not hits:
            continue
        matched.append({"claim_id": claim_id, "state": claim.state.value, "phrases": hits})
        if not claim.allowed_in_buyer_copy:
            blocked.append(claim_id)
    safe = not blocked
    return {
        "schema": "dio.m2.claim_phrase_guard.v1",
        "projection_digest": projection.projection_digest,
        "matched_claims": matched,
        "blocked_claims": sorted(set(blocked)),
        "safe_by_configured_guard": safe,
        "deterministic_phrase_guard_only": True,
        "autonomous_natural_language_claim_inference_claimed": False,
        "release_readiness": "CLAIM_LANGUAGE_SAFE_HELD_FOR_SEPARATE_AUTHORITY" if safe else "BLOCKED_CLAIM_LANGUAGE",
        "release_authority_created": False,
        "external_effects": False,
    }


def _run_phase2(repo_root: Path, work_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    parent = phase1_contract_receipt(repo_root)
    m1 = phase9_m1_receipt(repo_root)
    context = build_reference_commercial_context(repo_root)
    projection, offer, registration = build_commercial_projection(
        repo_root,
        context=context,
        work_root=work_root,
    )
    claim_map = {row.claim_id: row for row in projection.claims}
    safe_guard = evaluate_buyer_draft(
        repo_root,
        projection=projection,
        draft_text=(
            "Funding Proposal Studio prepares a controlled funding proposal pack. "
            "It is a governed metamorphic composition with one governed identity."
        ),
    )
    hostile_drafts = {
        "guarantee": "Funding Proposal Studio offers guaranteed funding approval.",
        "automatic_submission": "We automatically submits the pack and send the proposal on your behalf.",
        "wtp": "Proven willingness to pay means this offer is commercially validated.",
        "roi": "Funding Proposal Studio has proven ROI.",
        "dataflow": "End-to-end substantive dataflow is proven.",
    }
    hostile_results = {
        key: evaluate_buyer_draft(repo_root, projection=projection, draft_text=value)
        for key, value in hostile_drafts.items()
    }
    schema_path = repo_root / PROJECTION_SCHEMA_FILE
    schema_valid = False
    if schema_path.is_file():
        schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_valid = (
            schema_payload.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema_payload.get("$id") == "dio.commercial_projection.v1"
        )

    expected_held = {
        "proof.substantive_content_dataflow",
        "market.demand",
        "market.customer_acceptance",
        "market.willingness_to_pay",
        "market.commercial_validation",
        "market.repeatability",
        "market.roi",
    }
    expected_refused = {
        "prohibition.guaranteed_outcome",
        "prohibition.automatic_submission",
        "prohibition.external_authority",
        "prohibition.success_mints_authority",
    }
    supported = {row.claim_id for row in projection.supported_claims}
    held = {row.claim_id for row in projection.held_claims}
    refused = {row.claim_id for row in projection.refused_claims}
    lingua_reused = registration.get("schema") == "dio.lingua.product_registration_receipt.v1"
    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == config.get("required_parent_acceptance")
        and m1.get("passed") is True
        and m1.get("acceptance") == config.get("required_m1_acceptance")
        and m1.get("composite_unit", {}).get("unit_digest") == projection.unit_digest
        and schema_valid
        and lingua_reused
        and len(supported) >= 5
        and expected_held <= held
        and expected_refused <= refused
        and claim_map["proof.substantive_content_dataflow"].state == CommercialClaimState.HELD_UNPROVED
        and safe_guard.get("safe_by_configured_guard") is True
        and all(result.get("safe_by_configured_guard") is False for result in hostile_results.values())
        and projection.authority_created is False
        and projection.external_effects is False
    )
    return {
        "phase": "M2-2",
        "acceptance": M2_PHASE2_EXIT_TOKEN if passed else "DIO_M2_LINGUA_COMMERCIAL_PROJECTION_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "m1_parent_acceptance": m1.get("acceptance"),
        "m1_parent_verified": m1.get("passed") is True,
        "reference_product": context.product_id,
        "context_digest": context.context_digest,
        "world_lease_digest": context.world_lease_digest,
        "world_state_digest": context.world_state_digest,
        "market_state_digest": context.market_state_digest,
        "offer_state_digest": offer.offer_state_digest,
        "offer_lifecycle": offer.lifecycle.value,
        "projection_digest": projection.projection_digest,
        "projection_schema_valid": schema_valid,
        "semantic_object_id": projection.semantic_object_id,
        "lingua_source_document_hash": projection.lingua_source_document_hash,
        "lingua_existing_organ_reused": lingua_reused,
        "claim_extraction_mode": projection.claim_extraction_mode,
        "autonomous_natural_language_claim_inference_claimed": False,
        "deterministic_phrase_guard_only": True,
        "claim_count": len(projection.claims),
        "supported_claim_count": len(projection.supported_claims),
        "held_unproved_claim_count": len(projection.held_claims),
        "refused_claim_count": len(projection.refused_claims),
        "supported_claims": sorted(supported),
        "held_unproved_claims": sorted(held),
        "refused_claims": sorted(refused),
        "content_transform_dataflow_proved": m1.get("content_transform_dataflow_proved") is True,
        "content_transform_dataflow_claim_state": claim_map["proof.substantive_content_dataflow"].state.value,
        "market_response_observed": False,
        "payment_verified": False,
        "customer_acceptance_observed": False,
        "willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "safe_reference_guard": safe_guard,
        "hostile_guard_results": hostile_results,
        "release_authority_created": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


def phase2_projection_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase2(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-m2-phase2-") as temp:
        return _run_phase2(root, Path(temp))


__all__ = [
    "CommercialClaim",
    "CommercialClaimState",
    "CommercialProjection",
    "CommercialProjectionError",
    "DEFAULT_PROJECTION_CONFIG",
    "M2_PHASE2_EXIT_TOKEN",
    "build_commercial_projection",
    "build_reference_commercial_context",
    "evaluate_buyer_draft",
    "phase2_projection_receipt",
]
