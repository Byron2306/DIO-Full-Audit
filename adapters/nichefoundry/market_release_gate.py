"""Fail-closed authorization preflight for NicheFoundry market effects.

This module intentionally prepares no provider request.  A channel connector must
atomically consume its human or budget authority when it performs the external
action; a successful preflight is only evidence that the held package is eligible
to reach that boundary.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from adapters.legalis.decision_ledger import verify_decision
from adapters.legalis.service import canonical_hash


class MarketReleaseError(ValueError):
    """A held market package does not have the authority required by its surface."""


_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _ROOT / "config" / "nichefoundry_market_surface_policy.json"
_PAID_REQUIREMENT = "campaign_bound_legalis_and_one_use_budget_authority"
_ORGANIC_REQUIREMENT = "human_publication_approval"


def _policy_for(channel_id: str) -> Mapping[str, Any]:
    try:
        policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketReleaseError("NicheFoundry market surface policy is unavailable.") from exc
    for surface in policy.get("surfaces") or []:
        if isinstance(surface, Mapping) and surface.get("channel_id") == channel_id:
            return surface
    raise MarketReleaseError(f"Unknown NicheFoundry market channel: {channel_id!r}.")


def _required_text(value: Mapping[str, Any], key: str) -> str:
    result = str(value.get(key) or "").strip()
    if not result:
        raise MarketReleaseError(f"Market package requires {key}.")
    return result


def _package_binding(package: Mapping[str, Any]) -> dict[str, Any]:
    campaign_id = _required_text(package, "campaign_id")
    channel_id = _required_text(package, "channel_id")
    package_sha256 = _required_text(package, "package_sha256").lower()
    if len(package_sha256) != 64:
        raise MarketReleaseError("Market package_sha256 must be a SHA-256 hex digest.")
    return {"campaign_id": campaign_id, "channel_id": channel_id, "package_sha256": package_sha256}


def market_legalis_request(package: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact Legalis request a paid provider effect must be bound to."""
    binding = _package_binding(package)
    spend_minor = package.get("spend_minor")
    currency = str(package.get("currency") or "").strip().upper()
    if not isinstance(spend_minor, int) or isinstance(spend_minor, bool) or spend_minor <= 0 or not currency:
        raise MarketReleaseError("Paid market package requires positive integer spend_minor and currency.")
    return {
        "capability_id": "public_marketing_release",
        "market_effect": {**binding, "effect": "spend", "spend_minor": spend_minor, "currency": currency},
        "operator_checks": {"public_claim_review_complete": True},
        "valinor": {"entity_id": "dio-workflows", "operation": "write", "target": "public://marketing"},
    }


def _require_exact_binding(authority: Mapping[str, Any], binding: Mapping[str, Any], *, label: str) -> None:
    if authority.get("approved") is not True:
        raise MarketReleaseError(f"{label} is not approved.")
    for key, expected in binding.items():
        if authority.get(key) != expected:
            raise MarketReleaseError(f"{label} does not bind the same {key}.")


def _authorize_organic(binding: Mapping[str, Any], approval: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(approval, Mapping):
        raise MarketReleaseError("Organic publication requires a human publication approval.")
    _require_exact_binding(approval, binding, label="Human publication approval")
    approval_id = _required_text(approval, "approval_id")
    approver_id = _required_text(approval, "approver_id")
    return {"human_approval_id": approval_id, "approved_by": approver_id}


def _authorize_paid(
    state_root: Path,
    package: Mapping[str, Any],
    binding: Mapping[str, Any],
    *,
    legalis_decision_id: str | None,
    legalis_evidence_binding: Mapping[str, Any] | None,
    legalis_policy_version: str | None,
    budget_authority: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not legalis_decision_id or not isinstance(legalis_evidence_binding, Mapping) or not legalis_policy_version:
        raise MarketReleaseError("Paid spend requires a Legalis decision and its exact evidence binding.")
    request = market_legalis_request(package)
    verified = verify_decision(
        state_root,
        legalis_decision_id,
        expected_request_digest=canonical_hash(request),
        expected_evidence_digest=canonical_hash(legalis_evidence_binding),
        expected_capability="public_marketing_release",
        expected_policy_version=legalis_policy_version,
    )
    if (verified.get("decision") or {}).get("verdict") != "ALLOW":
        raise MarketReleaseError("Paid spend requires a Legalis ALLOW decision.")
    if not isinstance(budget_authority, Mapping):
        raise MarketReleaseError("Paid spend requires one-use budget authority.")
    _require_exact_binding(budget_authority, binding, label="Budget authority")
    if budget_authority.get("one_use") is not True or budget_authority.get("consumed") is True:
        raise MarketReleaseError("Budget authority must be unconsumed and one-use.")
    spend_minor = package["spend_minor"]
    if budget_authority.get("currency") != package.get("currency", "").upper() or budget_authority.get("max_spend_minor", 0) < spend_minor:
        raise MarketReleaseError("Budget authority does not cover this spend.")
    return {"legalis_decision_id": legalis_decision_id, "budget_authority_id": _required_text(budget_authority, "authority_id")}


def authorize_market_effect(
    state_root: Path,
    *,
    package: Mapping[str, Any],
    human_approval: Mapping[str, Any] | None = None,
    legalis_decision_id: str | None = None,
    legalis_evidence_binding: Mapping[str, Any] | None = None,
    legalis_policy_version: str | None = None,
    budget_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate exact authority bindings before a future provider connector executes."""
    binding = _package_binding(package)
    surface = _policy_for(binding["channel_id"])
    requirement = surface.get("release_requirement")
    if requirement == _ORGANIC_REQUIREMENT:
        authority = _authorize_organic(binding, human_approval)
    elif requirement == _PAID_REQUIREMENT:
        authority = _authorize_paid(
            Path(state_root), package, binding, legalis_decision_id=legalis_decision_id,
            legalis_evidence_binding=legalis_evidence_binding, legalis_policy_version=legalis_policy_version,
            budget_authority=budget_authority,
        )
    else:
        raise MarketReleaseError("Market surface has an unsupported release requirement.")
    return {
        "schema": "dio.nichefoundry.market_effect_preflight.v1",
        **binding,
        "effect": surface.get("effect"),
        "release_requirement": requirement,
        **authority,
        "provider_execution_enabled": False,
        "external_action_executed": False,
        "authority_created": False,
    }
