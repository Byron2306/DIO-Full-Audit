"""M2 Phase 3 channel, spend and release authority separation.

A commercially safe claim, a capable channel, a conversion, a payment, an
acceptance event or a planning-system release state is never authority by itself.
This phase binds those facts to the existing Seraph outbound gate and DIO
authority-plane laws without executing Seraph or creating any external effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from metamorphic.contracts import digest_payload, require_digest

from .contracts import ChannelAccessState, ChannelState
from .projection import (
    M2_PHASE2_EXIT_TOKEN,
    build_commercial_projection,
    build_reference_commercial_context,
    evaluate_buyer_draft,
    phase2_projection_receipt,
)


M2_PHASE3_EXIT_TOKEN = "DIO_M2_CHANNEL_AUTHORITY_SEPARATED"
DEFAULT_AUTHORITY_CONFIG = "config/m2_phase3_authority_separation.json"
AUTHORITY_SCHEMA_FILE = "schemas/dio.commercial_authority_preflight.v1.json"


class CommercialAuthorityError(RuntimeError):
    pass


class CommercialEffect(str, Enum):
    PUBLISH = "PUBLISH"
    SEND = "SEND"
    SPEND = "SPEND"
    PURCHASE = "PURCHASE"
    DEPLOY = "DEPLOY"
    DELIVER = "DELIVER"


class AuthorityDecision(str, Enum):
    REFUSE = "REFUSE"
    NEEDS_YOU = "NEEDS_YOU"
    ALLOW = "ALLOW"


@dataclass(frozen=True, slots=True)
class EffectAuthorityDecision:
    effect: CommercialEffect
    owner: str
    decision: AuthorityDecision
    reason: str
    authority_ref: str | None = None
    authority_created: bool = False
    schema: str = "dio.commercial_effect_authority_decision.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect", self.effect if isinstance(self.effect, CommercialEffect) else CommercialEffect(self.effect))
        object.__setattr__(self, "decision", self.decision if isinstance(self.decision, AuthorityDecision) else AuthorityDecision(self.decision))
        if str(self.owner).strip() != "Seraph":
            raise ValueError("commercial external-effect authority owner must be Seraph")
        if not str(self.reason or "").strip():
            raise ValueError("authority decision reason is required")
        if self.authority_created:
            raise ValueError("authority decisions may bind authority but may not create it")
        if self.authority_ref is not None:
            require_digest(self.authority_ref, field_name="authority_ref")
        if self.decision == AuthorityDecision.ALLOW and self.authority_ref is None:
            raise ValueError("ALLOW requires an externally supplied authority receipt digest")

    @property
    def decision_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "effect": self.effect.value,
            "owner": self.owner,
            "decision": self.decision.value,
            "reason": self.reason,
            "authority_ref": self.authority_ref,
            "authority_created": self.authority_created,
            "decision_digest": self.decision_digest,
        }


@dataclass(frozen=True, slots=True)
class CommercialAuthorityPreflight:
    context_digest: str
    projection_digest: str
    offer_state_digest: str
    channel_state_digest: str
    seraph_anchor_digest: str
    market_command_anchor_digest: str
    vesper_anchor_digest: str
    authority_plane_anchor_digest: str
    decisions: tuple[EffectAuthorityDecision, ...]
    claim_language_safe: bool
    market_command_planning_only: bool = True
    vesper_draft_only: bool = True
    seraph_operational_gate_executed: bool = False
    authority_created: bool = False
    external_effects: bool = False
    schema: str = "dio.commercial_authority_preflight.v1"

    def __post_init__(self) -> None:
        for field_name in (
            "context_digest", "projection_digest", "offer_state_digest", "channel_state_digest",
            "seraph_anchor_digest", "market_command_anchor_digest", "vesper_anchor_digest",
            "authority_plane_anchor_digest",
        ):
            require_digest(getattr(self, field_name), field_name=field_name)
        if len(self.decisions) != len(CommercialEffect):
            raise ValueError("preflight requires exactly one decision for each commercial external effect")
        effects = [row.effect for row in self.decisions]
        if len(set(effects)) != len(effects) or set(effects) != set(CommercialEffect):
            raise ValueError("commercial effect decisions must be unique and complete")
        if any(row.owner != "Seraph" for row in self.decisions):
            raise ValueError("every commercial external effect must remain Seraph-owned")
        if self.authority_created or self.external_effects:
            raise ValueError("authority preflight may not create authority or external effects")
        if self.seraph_operational_gate_executed:
            raise ValueError("M2-3 is a binding/separation proof, not operational egress execution")

    @property
    def preflight_digest(self) -> str:
        return digest_payload(self)

    @property
    def any_effect_allowed(self) -> bool:
        return any(row.decision == AuthorityDecision.ALLOW for row in self.decisions)

    def decision_for(self, effect: CommercialEffect | str) -> EffectAuthorityDecision:
        target = effect if isinstance(effect, CommercialEffect) else CommercialEffect(effect)
        return next(row for row in self.decisions if row.effect == target)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "context_digest": self.context_digest,
            "projection_digest": self.projection_digest,
            "offer_state_digest": self.offer_state_digest,
            "channel_state_digest": self.channel_state_digest,
            "seraph_anchor_digest": self.seraph_anchor_digest,
            "market_command_anchor_digest": self.market_command_anchor_digest,
            "vesper_anchor_digest": self.vesper_anchor_digest,
            "authority_plane_anchor_digest": self.authority_plane_anchor_digest,
            "decisions": [row.to_dict() for row in self.decisions],
            "claim_language_safe": self.claim_language_safe,
            "market_command_planning_only": self.market_command_planning_only,
            "vesper_draft_only": self.vesper_draft_only,
            "seraph_operational_gate_executed": self.seraph_operational_gate_executed,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "any_effect_allowed": self.any_effect_allowed,
            "preflight_digest": self.preflight_digest,
        }


def _load_config(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_AUTHORITY_CONFIG
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialAuthorityError(f"cannot load M2-3 authority config: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != "dio.m2.commercial_authority_separation_config.v1":
        raise CommercialAuthorityError("unsupported M2-3 authority config")
    return value


def _file_digest(path: Path) -> str:
    if not path.is_file():
        raise CommercialAuthorityError(f"required authority anchor missing: {path}")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _anchor_truth(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    anchors = config.get("anchors") or {}
    required = {"seraph", "market_command", "vesper", "authority_plane"}
    if set(anchors) != required:
        raise CommercialAuthorityError("M2-3 authority anchors are incomplete")
    paths = {key: root / str(value) for key, value in anchors.items()}
    texts = {key: path.read_text(encoding="utf-8") for key, path in paths.items()}
    plane = json.loads(texts["authority_plane"])
    laws = plane.get("laws") or {}
    checks = {
        "seraph_gate_action_present": "async def gate_action(" in texts["seraph"],
        "seraph_world_state_bound": "world_manifold" in texts["seraph"],
        "seraph_vns_bound": "from backend.services.vns import vns" in texts["seraph"],
        "seraph_arda_bound": "get_arda_fabric" in texts["seraph"],
        "market_command_automatic_spend_off": '"automatic_spend": "off"' in texts["market_command"],
        "market_command_publication_approval_required": '"organic_publication": "approval_required"' in texts["market_command"],
        "vesper_draft_only": "`DRAFT_ONLY`" in texts["vesper"],
        "vesper_send_authorized_false": "`send_authorized: false`" in texts["vesper"],
        "vesper_sent_false": "`sent: false`" in texts["vesper"],
        "authority_plane_evidence_not_authority": laws.get("evidence_is_not_authority") is True,
        "authority_plane_legalis_not_execution_authority": laws.get("legalis_allow_is_not_execution_authority") is True,
        "authority_plane_capability_lease_not_self_authorizing": laws.get("capability_lease_is_not_self_authorizing") is True,
    }
    return {
        "digests": {key: _file_digest(path) for key, path in paths.items()},
        "checks": checks,
        "valid": all(checks.values()),
    }


def _build_channel_state(context: Any, config: Mapping[str, Any]) -> ChannelState:
    row = config.get("reference_channel") or {}
    if str(row.get("channel_id") or "") != context.channel_id:
        raise CommercialAuthorityError("reference channel does not match CommercialContext")
    return ChannelState(
        channel_state_id=f"CHANSTATE-{context.context_digest.split(':', 1)[1][:16]}",
        channel_id=context.channel_id,
        context_digest=context.context_digest,
        access_state=ChannelAccessState(str(row.get("access_state") or "")),
        read_capability_present=bool(row.get("read_capability_present")),
        draft_capability_present=bool(row.get("draft_capability_present")),
        publish_capability_present=bool(row.get("publish_capability_present")),
        spend_capability_present=bool(row.get("spend_capability_present")),
        required_authority_refs=tuple(str(value) for value in (row.get("required_authority_refs") or [])),
        evidence_refs=(),
        authority_created=False,
    )


def build_reference_authority_preflight(
    repo_root: str | Path,
    *,
    work_root: str | Path,
) -> tuple[CommercialAuthorityPreflight, ChannelState, dict[str, Any]]:
    root = Path(repo_root).resolve()
    config = _load_config(root)
    parent = phase2_projection_receipt(root)
    if parent.get("passed") is not True or parent.get("acceptance") != config.get("required_parent_acceptance"):
        raise CommercialAuthorityError("M2-2 parent projection is not verified")
    context = build_reference_commercial_context(root)
    projection, offer, _registration = build_commercial_projection(root, context=context, work_root=work_root)
    safe_guard = evaluate_buyer_draft(
        root,
        projection=projection,
        draft_text=(
            "Funding Proposal Studio prepares a controlled funding proposal pack. "
            "It is a governed metamorphic composition with one governed identity."
        ),
    )
    if safe_guard.get("safe_by_configured_guard") is not True:
        raise CommercialAuthorityError("reference buyer copy is not claim-safe")
    channel = _build_channel_state(context, config)
    anchors = _anchor_truth(root, config)
    if not anchors["valid"]:
        raise CommercialAuthorityError("canonical authority anchors do not satisfy M2-3 requirements")

    decisions: list[EffectAuthorityDecision] = []
    effect_specs = config.get("effects") or []
    if len(effect_specs) != len(CommercialEffect):
        raise CommercialAuthorityError("M2-3 requires one configured decision per commercial external effect")
    for spec in effect_specs:
        effect = CommercialEffect(str(spec.get("effect") or ""))
        decision = AuthorityDecision(str(spec.get("reference_decision") or ""))
        decisions.append(
            EffectAuthorityDecision(
                effect=effect,
                owner=str(spec.get("owner") or ""),
                decision=decision,
                reason="controlled reference has no externally supplied Seraph authority receipt for this effect",
                authority_ref=None,
                authority_created=False,
            )
        )

    preflight = CommercialAuthorityPreflight(
        context_digest=context.context_digest,
        projection_digest=projection.projection_digest,
        offer_state_digest=offer.offer_state_digest,
        channel_state_digest=channel.channel_state_digest,
        seraph_anchor_digest=anchors["digests"]["seraph"],
        market_command_anchor_digest=anchors["digests"]["market_command"],
        vesper_anchor_digest=anchors["digests"]["vesper"],
        authority_plane_anchor_digest=anchors["digests"]["authority_plane"],
        decisions=tuple(decisions),
        claim_language_safe=True,
        market_command_planning_only=True,
        vesper_draft_only=True,
        seraph_operational_gate_executed=False,
        authority_created=False,
        external_effects=False,
    )
    return preflight, channel, anchors


def evaluate_non_authority_influences(
    preflight: CommercialAuthorityPreflight,
    *,
    claim_language_safe: bool = False,
    conversion_observed: bool = False,
    verified_payment: bool = False,
    customer_acceptance: bool = False,
    market_command_release_state: bool = False,
    legalis_allow: bool = False,
    beast_market_crystal: bool = False,
    harmonic_normal_flow: bool = False,
) -> dict[str, Any]:
    influences = {
        "claim_language_safe": bool(claim_language_safe),
        "conversion_observed": bool(conversion_observed),
        "verified_payment": bool(verified_payment),
        "customer_acceptance": bool(customer_acceptance),
        "market_command_release_state": bool(market_command_release_state),
        "legalis_allow": bool(legalis_allow),
        "beast_market_crystal": bool(beast_market_crystal),
        "harmonic_normal_flow": bool(harmonic_normal_flow),
    }
    return {
        "schema": "dio.m2.non_authority_influence_check.v1",
        "preflight_digest": preflight.preflight_digest,
        "influences": influences,
        "decisions_unchanged": {row.effect.value: row.decision.value for row in preflight.decisions},
        "any_effect_allowed": preflight.any_effect_allowed,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
    }


def _run_phase3(repo_root: Path, work_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    parent = phase2_projection_receipt(repo_root)
    preflight, channel, anchors = build_reference_authority_preflight(
        repo_root,
        work_root=work_root / "projection",
    )
    all_influences = evaluate_non_authority_influences(
        preflight,
        claim_language_safe=True,
        conversion_observed=True,
        verified_payment=True,
        customer_acceptance=True,
        market_command_release_state=True,
        legalis_allow=True,
        beast_market_crystal=True,
        harmonic_normal_flow=True,
    )
    schema_path = repo_root / AUTHORITY_SCHEMA_FILE
    schema_valid = False
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_valid = (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema.get("$id") == "dio.commercial_authority_preflight.v1"
        )
    decisions = {row.effect.value: row.decision.value for row in preflight.decisions}
    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == config.get("required_parent_acceptance")
        and schema_valid
        and anchors.get("valid") is True
        and channel.access_state == ChannelAccessState.DRAFT_ONLY
        and channel.draft_capability_present is True
        and channel.publish_capability_present is True
        and channel.authority_created is False
        and all(value == AuthorityDecision.REFUSE.value for value in decisions.values())
        and preflight.claim_language_safe is True
        and preflight.any_effect_allowed is False
        and all_influences.get("any_effect_allowed") is False
        and preflight.seraph_operational_gate_executed is False
        and preflight.authority_created is False
        and preflight.external_effects is False
    )
    return {
        "phase": "M2-3",
        "acceptance": M2_PHASE3_EXIT_TOKEN if passed else "DIO_M2_CHANNEL_AUTHORITY_SEPARATION_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": parent.get("reference_product"),
        "context_digest": preflight.context_digest,
        "projection_digest": preflight.projection_digest,
        "offer_state_digest": preflight.offer_state_digest,
        "channel_state_digest": preflight.channel_state_digest,
        "channel_access_state": channel.access_state.value,
        "channel_read_capability_present": channel.read_capability_present,
        "channel_draft_capability_present": channel.draft_capability_present,
        "channel_publish_capability_present": channel.publish_capability_present,
        "channel_spend_capability_present": channel.spend_capability_present,
        "capability_is_authority": False,
        "claim_language_safe": preflight.claim_language_safe,
        "safe_claim_is_release_authority": False,
        "conversion_is_spend_authority": False,
        "payment_is_delivery_authority": False,
        "acceptance_is_product_authority": False,
        "market_command_release_is_egress_authority": False,
        "legalis_allow_is_release_authority": False,
        "beast_crystal_is_release_authority": False,
        "harmonic_normal_flow_is_release_authority": False,
        "seraph_owns_external_effect_authority": True,
        "seraph_anchor_digest": preflight.seraph_anchor_digest,
        "seraph_operational_gate_executed": False,
        "effect_decisions": decisions,
        "all_external_effects_refused": all(value == "REFUSE" for value in decisions.values()),
        "effect_authority_slots_separate": len(decisions) == len(CommercialEffect),
        "authority_anchor_checks": anchors["checks"],
        "authority_schema_valid": schema_valid,
        "preflight_digest": preflight.preflight_digest,
        "non_authority_influence_check": all_influences,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


def phase3_authority_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase3(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-m2-phase3-") as temp:
        return _run_phase3(root, Path(temp))


__all__ = [
    "AUTHORITY_SCHEMA_FILE",
    "AuthorityDecision",
    "CommercialAuthorityError",
    "CommercialAuthorityPreflight",
    "CommercialEffect",
    "DEFAULT_AUTHORITY_CONFIG",
    "EffectAuthorityDecision",
    "M2_PHASE3_EXIT_TOKEN",
    "build_reference_authority_preflight",
    "evaluate_non_authority_influences",
    "phase3_authority_receipt",
]
