from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

BEAST_CODE_ROOT = (
    REPO_ROOT
    / "cross_folder_variants"
    / "EdgeK-BEAST"
    / "A_CODE"
)

PUBLIC_DOMAIN = "vesper_public"
OPERATOR_DOMAIN = "vesper_operator"

SCHEMA = "dio.vesper.semantic_context.v1"


def _beast_api() -> dict[str, Any]:
    if not BEAST_CODE_ROOT.exists():
        raise RuntimeError(
            "BEAST semantic runtime is unavailable"
        )

    if str(BEAST_CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(BEAST_CODE_ROOT))

    from app.kernel.compute.residual_contracts import (
        sha256_digest,
    )
    from app.kernel.compute.semantic_generalizer import (
        SemanticReuseKey,
        normalize_utterance,
        semantic_intent_fingerprint,
    )

    return {
        "sha256_digest": sha256_digest,
        "SemanticReuseKey": SemanticReuseKey,
        "normalize_utterance": normalize_utterance,
        "semantic_intent_fingerprint":
            semantic_intent_fingerprint,
    }


def _mapping(
    name: str,
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if value is None:
        raise ValueError(
            f"{name} must be supplied from current context"
        )

    if not isinstance(value, Mapping):
        raise TypeError(
            f"{name} must be a mapping"
        )

    return dict(value)


def _buyer_scope_state(
    *,
    conversation_state: Mapping[str, Any],
    commercial: Mapping[str, Any],
) -> str:
    pricing = commercial.get("pricing") or {}

    if isinstance(pricing, Mapping):
        tier = pricing.get("selected_tier") or {}

        if (
            isinstance(tier, Mapping)
            and tier.get("tier_id")
        ):
            return "ESTABLISHED_DEFEASIBLE"

    constraints = (
        conversation_state.get("known_constraints")
        or []
    )

    for constraint in constraints:
        if (
            isinstance(constraint, str)
            and constraint.startswith("buyer_scope:")
        ):
            return "ESTABLISHED_DEFEASIBLE"

        if (
            isinstance(constraint, Mapping)
            and constraint.get("kind")
                == "buyer_scope"
            and constraint.get("value")
        ):
            return "ESTABLISHED_DEFEASIBLE"

    return "UNKNOWN"


def _buyer_scope_value(
    conversation_state: Mapping[str, Any],
) -> str | None:
    """Return the previously persisted buyer-scope value, if any."""

    constraints = (
        conversation_state.get("known_constraints")
        or []
    )

    for constraint in constraints:
        if (
            isinstance(constraint, str)
            and constraint.startswith("buyer_scope:")
        ):
            value = constraint.split(":", 1)[1].strip()

            if value:
                return value

        if (
            isinstance(constraint, Mapping)
            and constraint.get("kind") == "buyer_scope"
            and constraint.get("value")
        ):
            return str(
                constraint.get("value")
            ).strip() or None

    return None


def _explicit_current_buyer_scope(
    commercial: Mapping[str, Any],
) -> str | None:
    """Return current explicit scope only.

    Context-inherited commercial scope is deliberately excluded.
    """

    pricing = commercial.get("pricing") or {}

    if not isinstance(pricing, Mapping):
        return None

    if (
        str(pricing.get("tier_basis") or "")
        != "EXPLICIT_MESSAGE"
    ):
        return None

    tier = pricing.get("selected_tier") or {}

    if not isinstance(tier, Mapping):
        return None

    tier_id = str(
        tier.get("tier_id") or ""
    ).strip()

    return tier_id or None


def _buyer_scope_transition(
    *,
    semantic_continuity: Mapping[str, Any],
    conversation_state: Mapping[str, Any],
    commercial: Mapping[str, Any],
) -> str:
    """Classify buyer-scope change without encoding tier values."""

    if (
        str(
            semantic_continuity.get("speech_act")
            or ""
        )
        != "BUYER_SCOPE_REFINEMENT"
    ):
        return "NOT_APPLICABLE"

    previous = _buyer_scope_value(
        conversation_state
    )

    current = _explicit_current_buyer_scope(
        commercial
    )

    if current is None:
        return "UNKNOWN"

    if previous is None:
        return "ESTABLISH"

    if previous == current:
        return "RETAIN"

    return "OVERRIDE"


def _public_semantic_payload(
    *,
    semantic_continuity: Mapping[str, Any],
    conversation_state: Mapping[str, Any],
    commercial: Mapping[str, Any],
) -> dict[str, Any]:
    raw_referent = (
        semantic_continuity.get("active_referent")
    )

    referent_kind = None
    referent_value = None

    if isinstance(raw_referent, Mapping):
        referent_kind = (
            str(raw_referent.get("kind"))
            if raw_referent.get("kind")
            else None
        )
        referent_value = (
            raw_referent.get("value")
        )

    elif isinstance(raw_referent, str):
        cleaned = raw_referent.strip()

        if cleaned:
            referent_value = cleaned

            commercial_product = (
                commercial.get("product")
                or {}
            )

            if (
                isinstance(
                    commercial_product,
                    Mapping,
                )
                and str(
                    commercial_product.get("name")
                    or ""
                ).strip()
                == cleaned
            ):
                referent_kind = "product"
            else:
                referent_kind = "referent"

    commercial_state = str(
        commercial.get("state")
        or "UNKNOWN"
    )

    payload = {
        "semantic_domain": PUBLIC_DOMAIN,
        "relation": str(
            semantic_continuity.get("relation")
            or "UNRESOLVED"
        ),
        "speech_act": str(
            semantic_continuity.get("speech_act")
            or "UNRESOLVED"
        ),
        "referent_kind": referent_kind,
        "active_referent_present": bool(
            referent_value
        ),
        "buyer_scope_state": _buyer_scope_state(
            conversation_state=conversation_state,
            commercial=commercial,
        ),
        "commercial_resolution": (
            "AMBIGUOUS"
            if commercial_state
                == "NEEDS_CLARIFICATION"
            else commercial_state
        ),
    }

    if (
        payload["speech_act"]
        == "BUYER_SCOPE_REFINEMENT"
    ):
        payload["buyer_scope_transition"] = (
            _buyer_scope_transition(
                semantic_continuity=
                    semantic_continuity,
                conversation_state=
                    conversation_state,
                commercial=commercial,
            )
        )

    return payload


def _operator_semantic_payload(
    *,
    text: str,
    decision: Mapping[str, Any],
    semantic_intent_fingerprint,
) -> dict[str, Any]:
    """Build Vesper operator semantic identity.

    The trusted deterministic operator route defines the reusable
    semantic class. The raw BEAST lexical fingerprint describes the
    surface form only and must not fragment equivalent routed intents.

    Operator semantic reuse never grants execution authority.
    """
    route_intent = str(
        decision.get("intent")
        or "unknown"
    )

    return {
        "semantic_domain": OPERATOR_DOMAIN,
        "operator_semantic_class": route_intent,
        "route_intent": route_intent,
    }


def build_current_semantic_context(
    *,
    role: str,
    text: str,
    semantic_continuity: Mapping[str, Any] | None,
    conversation_state: Mapping[str, Any] | None,
    commercial: Mapping[str, Any] | None,
    decision: Mapping[str, Any] | None,
    world_state: Mapping[str, Any] | None,
    capabilities: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
    temporal_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a reuse key exclusively from CURRENT context.

    No field is copied from a candidate semantic crystal.

    Public Vesper derives semantic identity from Lingua's
    verified conversational frame.

    Operator Vesper retains BEAST's bounded operator-language
    fingerprint.

    Semantic reuse never creates execution, send, spend,
    payment, fulfilment or release authority.
    """

    api = _beast_api()
    digest = api["sha256_digest"]

    role = str(role or "").strip().casefold()

    if role not in {"public", "operator"}:
        raise ValueError(
            "role must be public or operator"
        )

    text = str(text or "").strip()

    if not text:
        raise ValueError(
            "semantic context requires utterance text"
        )

    state = _mapping(
        "conversation_state",
        conversation_state,
    )

    commercial_now = _mapping(
        "commercial",
        commercial,
    )

    decision_now = _mapping(
        "decision",
        decision,
    )

    world_now = _mapping(
        "world_state",
        world_state,
    )

    capabilities_now = _mapping(
        "capabilities",
        capabilities,
    )

    evidence_now = _mapping(
        "evidence",
        evidence,
    )

    policy_now = _mapping(
        "policy",
        policy,
    )

    temporal_now = _mapping(
        "temporal_scope",
        temporal_scope,
    )

    if role == "public":
        lingua = _mapping(
            "semantic_continuity",
            semantic_continuity,
        )

        semantic_domain = PUBLIC_DOMAIN

        semantic_payload = (
            _public_semantic_payload(
                semantic_continuity=lingua,
                conversation_state=state,
                commercial=commercial_now,
            )
        )

        discourse_payload = {
            "semantic_domain": semantic_domain,
            "relation": semantic_payload[
                "relation"
            ],
            "speech_act": semantic_payload[
                "speech_act"
            ],
            "referent_kind": semantic_payload[
                "referent_kind"
            ],
            "active_referent_present":
                semantic_payload[
                    "active_referent_present"
                ],
            "buyer_scope_state":
                semantic_payload[
                    "buyer_scope_state"
                ],
            "commercial_resolution":
                semantic_payload[
                    "commercial_resolution"
                ],
        }

    else:
        semantic_domain = OPERATOR_DOMAIN

        semantic_payload = (
            _operator_semantic_payload(
                text=text,
                decision=decision_now,
                semantic_intent_fingerprint=(
                    api[
                        "semantic_intent_fingerprint"
                    ]
                ),
            )
        )

        discourse_payload = {
            "semantic_domain": semantic_domain,
            "route_intent": semantic_payload[
                "route_intent"
            ],
            "operator_semantic_class":
                semantic_payload[
                    "operator_semantic_class"
                ],
        }

    semantic_fingerprint_digest = digest(
        semantic_payload
    )

    normalized_utterance_digest = digest(
        api["normalize_utterance"](text)
    )

    schema_digest = digest(
        {
            "schema": SCHEMA,
            "semantic_domain": semantic_domain,
        }
    )

    discourse_digest = digest(
        discourse_payload
    )

    world_digest = digest(
        {
            "semantic_domain": semantic_domain,
            "current_world": world_now,
        }
    )

    capability_digest = digest(
        {
            "semantic_domain": semantic_domain,
            "current_capabilities":
                capabilities_now,
        }
    )

    evidence_digest = digest(
        {
            "semantic_domain": semantic_domain,
            "current_evidence": evidence_now,
        }
    )

    policy_digest = digest(
        {
            "semantic_domain": semantic_domain,
            "current_policy": policy_now,
        }
    )

    temporal_scope_digest = digest(
        {
            "semantic_domain": semantic_domain,
            "current_temporal_scope":
                temporal_now,
        }
    )

    key = api["SemanticReuseKey"](
        semantic_fingerprint_digest=(
            semantic_fingerprint_digest
        ),
        normalized_utterance_digest=(
            normalized_utterance_digest
        ),
        schema_digest=schema_digest,
        discourse_digest=discourse_digest,
        world_digest=world_digest,
        capability_digest=capability_digest,
        evidence_digest=evidence_digest,
        policy_digest=policy_digest,
        temporal_scope_digest=(
            temporal_scope_digest
        ),
    )

    return {
        "schema": SCHEMA,
        "semantic_domain": semantic_domain,
        "role": role,
        "semantic_payload": semantic_payload,
        "discourse": discourse_payload,
        "reuse_key": key,
        "semantic_match_digest":
            key.semantic_match_digest,
        "surface_key_digest":
            key.key_digest,
        "authority_created": False,
        "external_effects": False,
        "truth_boundary": (
            "Semantic context describes current meaning "
            "and applicability only. It does not create "
            "execution, send, spend, payment, fulfilment "
            "or release authority."
        ),
    }
