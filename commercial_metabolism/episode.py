"""M2 Phase 4 governed market-episode compiler.

This phase turns the verified commercial meaning and authority preflight into a
complete commercial intention. It reuses Market Command to materialise only a
local DRAFT/HELD planning record. It does not activate a campaign, execute
Seraph, publish, send, spend, purchase, deploy, deliver, fabricate observations,
or claim commercial validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from market_command.core import MarketStore
from metamorphic.contracts import digest_payload, require_digest

from .authority import M2_PHASE3_EXIT_TOKEN, phase3_authority_receipt
from .contracts import MarketObservationKind, PricingEvidenceState, PricingHypothesisState


M2_PHASE4_EXIT_TOKEN = "DIO_M2_MARKET_EPISODE_READY"
DEFAULT_EPISODE_CONFIG = "config/m2_phase4_market_episode.json"
EPISODE_SCHEMA_FILE = "schemas/dio.market_episode_plan.v1.json"


class MarketEpisodeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MarketEpisodePlan:
    episode_id: str
    product_id: str
    context_digest: str
    projection_digest: str
    offer_state_digest: str
    channel_state_digest: str
    pricing_state_digest: str
    authority_preflight_digest: str
    market_command_plan_digest: str
    observation_contract_digest: str
    campaign_id: str
    buyer_segment_id: str
    channel_id: str
    offer_id: str
    currency: str
    price_minor: int
    measurement_window_seconds: int
    release_state: str
    observation_kinds: tuple[str, ...]
    market_response_observed: bool = False
    activation_performed: bool = False
    seraph_operational_gate_executed: bool = False
    authority_created: bool = False
    external_effects: bool = False
    schema: str = "dio.market_episode_plan.v1"

    def __post_init__(self) -> None:
        for field_name in (
            "episode_id", "product_id", "campaign_id", "buyer_segment_id", "channel_id",
            "offer_id", "currency", "release_state",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        for field_name in (
            "context_digest", "projection_digest", "offer_state_digest", "channel_state_digest",
            "pricing_state_digest", "authority_preflight_digest", "market_command_plan_digest",
            "observation_contract_digest",
        ):
            require_digest(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.price_minor, int) or isinstance(self.price_minor, bool) or self.price_minor < 0:
            raise ValueError("price_minor must be a non-negative integer")
        if not isinstance(self.measurement_window_seconds, int) or self.measurement_window_seconds <= 0:
            raise ValueError("measurement_window_seconds must be positive")
        if set(self.observation_kinds) != {row.value for row in MarketObservationKind}:
            raise ValueError("market episode must declare the complete observation vocabulary")
        if self.market_response_observed:
            raise ValueError("M2-4 compiles observation intent but may not fabricate market response")
        if self.activation_performed or self.seraph_operational_gate_executed:
            raise ValueError("M2-4 may not activate or execute Seraph")
        if self.authority_created or self.external_effects:
            raise ValueError("M2-4 may not create authority or external effects")
        if self.release_state != "HELD_FOR_AUTHORITY":
            raise ValueError("M2-4 controlled reference must remain HELD_FOR_AUTHORITY")

    @property
    def plan_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "episode_id": self.episode_id,
            "product_id": self.product_id,
            "context_digest": self.context_digest,
            "projection_digest": self.projection_digest,
            "offer_state_digest": self.offer_state_digest,
            "channel_state_digest": self.channel_state_digest,
            "pricing_state_digest": self.pricing_state_digest,
            "authority_preflight_digest": self.authority_preflight_digest,
            "market_command_plan_digest": self.market_command_plan_digest,
            "observation_contract_digest": self.observation_contract_digest,
            "campaign_id": self.campaign_id,
            "buyer_segment_id": self.buyer_segment_id,
            "channel_id": self.channel_id,
            "offer_id": self.offer_id,
            "currency": self.currency,
            "price_minor": self.price_minor,
            "measurement_window_seconds": self.measurement_window_seconds,
            "release_state": self.release_state,
            "observation_kinds": list(self.observation_kinds),
            "market_response_observed": self.market_response_observed,
            "activation_performed": self.activation_performed,
            "seraph_operational_gate_executed": self.seraph_operational_gate_executed,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "plan_digest": self.plan_digest,
        }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketEpisodeError(f"cannot load market-episode source: {path}") from exc
    if not isinstance(value, dict):
        raise MarketEpisodeError(f"market-episode source must be an object: {path}")
    return value


def _load_config(root: Path) -> dict[str, Any]:
    value = _load_json(root / DEFAULT_EPISODE_CONFIG)
    if value.get("schema") != "dio.m2.market_episode_config.v1":
        raise MarketEpisodeError("unsupported M2-4 market episode config")
    return value


def _reference_rows(root: Path, config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    phase2 = _load_json(root / str(config.get("phase2_projection_config") or ""))
    phase3 = _load_json(root / str(config.get("phase3_authority_config") or ""))
    if phase2.get("schema") != "dio.m2.commercial_projection_config.v1":
        raise MarketEpisodeError("M2-4 phase2 config anchor is invalid")
    if phase3.get("schema") != "dio.m2.commercial_authority_separation_config.v1":
        raise MarketEpisodeError("M2-4 phase3 config anchor is invalid")
    ref = phase2.get("reference_context") or {}
    channel = phase3.get("reference_channel") or {}
    if str(ref.get("channel_id") or "") != str(channel.get("channel_id") or ""):
        raise MarketEpisodeError("M2-2 and M2-3 channel anchors diverge")
    return ref, channel


def _build_pricing_state(parent: Mapping[str, Any], ref: Mapping[str, Any]) -> PricingHypothesisState:
    context_digest = str(parent.get("context_digest") or "")
    suffix = context_digest.split(":", 1)[-1][:16]
    return PricingHypothesisState(
        pricing_state_id=f"PRICESTATE-{suffix}",
        hypothesis_id=f"PRICE-{suffix}",
        context_digest=context_digest,
        amount_minor=int(ref.get("price_minor") or 0),
        currency=str(ref.get("currency") or ""),
        evidence_state=PricingEvidenceState.UNTESTED,
        exposure_count=0,
        verified_payment_count=0,
        accepted_customer_count=0,
        evidence_refs=(),
    )


def _observation_contract(parent: Mapping[str, Any], episode_cfg: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "schema": "dio.m2.market_observation_contract.v1",
        "context_digest": str(parent.get("context_digest") or ""),
        "projection_digest": str(parent.get("projection_digest") or ""),
        "offer_state_digest": str(parent.get("offer_state_digest") or ""),
        "channel_state_digest": str(parent.get("channel_state_digest") or ""),
        "source": str(episode_cfg.get("observation_source") or ""),
        "measurement_window_seconds": int(episode_cfg.get("measurement_window_seconds") or 0),
        "observation_kinds": [row.value for row in MarketObservationKind],
        "silence_rule": str(episode_cfg.get("silence_rule") or ""),
        "no_response_requires_closed_window": True,
        "market_response_observed": False,
        "fabricated_observations_allowed": False,
    }
    payload["observation_contract_digest"] = digest_payload(payload)
    return payload


def _market_command_spec(
    parent: Mapping[str, Any],
    ref: Mapping[str, Any],
    episode_cfg: Mapping[str, Any],
    pricing: PricingHypothesisState,
    observation_contract: Mapping[str, Any],
) -> dict[str, Any]:
    context_digest = str(parent.get("context_digest") or "")
    campaign_id = "M2P4-" + context_digest.split(":", 1)[-1][:20].upper()
    spec = {
        "campaign_id": campaign_id,
        "product_line_id": str(parent.get("reference_product") or ""),
        "offer_id": str(ref.get("offer_id") or ""),
        "name": str(episode_cfg.get("name") or ""),
        "audience": str(ref.get("buyer_segment_id") or ""),
        "channel_id": str(ref.get("channel_id") or ""),
        "mode": str(episode_cfg.get("mode") or "experiment"),
        "objective": str(episode_cfg.get("objective") or ""),
        "budget_cap_minor": int(episode_cfg.get("market_command_budget_cap_minor") or 0),
        "currency": str(ref.get("currency") or ""),
        "experiment_window_days": int(episode_cfg.get("market_command_default_experiment_window_days") or 1),
        "proof_asset": str(parent.get("projection_digest") or ""),
        "creative_brief": str(episode_cfg.get("content_policy") or ""),
        "source_lineage": {
            "context_digest": context_digest,
            "projection_digest": str(parent.get("projection_digest") or ""),
            "offer_state_digest": str(parent.get("offer_state_digest") or ""),
            "channel_state_digest": str(parent.get("channel_state_digest") or ""),
            "preflight_digest": str(parent.get("preflight_digest") or ""),
            "pricing_state_digest": pricing.pricing_state_digest,
            "observation_contract_digest": str(observation_contract.get("observation_contract_digest") or ""),
        },
        "source_gates": {
            "m2_phase3_verified": True,
            "claim_language_safe": bool(parent.get("claim_language_safe")),
            "all_external_effects_refused": bool(parent.get("all_external_effects_refused")),
            "seraph_operational_gate_executed": bool(parent.get("seraph_operational_gate_executed")),
        },
    }
    return spec


def compile_reference_market_episode(
    repo_root: str | Path,
    *,
    work_root: str | Path,
) -> tuple[MarketEpisodePlan, PricingHypothesisState, dict[str, Any], dict[str, Any]]:
    root = Path(repo_root).resolve()
    target = Path(work_root).resolve()
    target.mkdir(parents=True, exist_ok=True)
    config = _load_config(root)
    parent = phase3_authority_receipt(root)
    if parent.get("passed") is not True or parent.get("acceptance") != config.get("required_parent_acceptance"):
        raise MarketEpisodeError("M2-3 authority separation parent is not verified")
    if parent.get("all_external_effects_refused") is not True or parent.get("seraph_operational_gate_executed") is not False:
        raise MarketEpisodeError("M2-4 controlled reference requires a fully held M2-3 preflight")

    ref, _channel = _reference_rows(root, config)
    episode_cfg = config.get("episode") or {}
    pricing = _build_pricing_state(parent, ref)
    observation_contract = _observation_contract(parent, episode_cfg)
    spec = _market_command_spec(parent, ref, episode_cfg, pricing, observation_contract)
    plan_digest = digest_payload({"schema": "dio.m2.market_command_plan.v1", "spec": spec})

    store = MarketStore(
        db_path=target / "market_command" / "market.sqlite3",
        event_log=target / "market_command" / "events.jsonl",
        config={
            "max_experiment_budget_minor": 0,
            "default_experiment_window_days": int(episode_cfg.get("market_command_default_experiment_window_days") or 1),
            "require_approved_content_for_activation": False,
        },
    )
    campaign = store.create_campaign(spec)
    policy = store.policy()
    if campaign.get("state") != "draft" or campaign.get("approval_state") != "pending" or campaign.get("publication_state") != "held":
        raise MarketEpisodeError("Market Command did not preserve DRAFT/HELD planning state")
    if int(campaign.get("budget_cap_minor") or 0) != 0 or policy.get("automatic_spend") != "off":
        raise MarketEpisodeError("M2-4 Market Command planning state violated spend boundary")

    context_digest = str(parent.get("context_digest") or "")
    episode_id = "episode:market:" + digest_payload({
        "context": context_digest,
        "projection": parent.get("projection_digest"),
        "pricing": pricing.pricing_state_digest,
        "preflight": parent.get("preflight_digest"),
        "market_plan": plan_digest,
        "observation": observation_contract["observation_contract_digest"],
    }).split(":", 1)[1][:24]
    plan = MarketEpisodePlan(
        episode_id=episode_id,
        product_id=str(parent.get("reference_product") or ""),
        context_digest=context_digest,
        projection_digest=str(parent.get("projection_digest") or ""),
        offer_state_digest=str(parent.get("offer_state_digest") or ""),
        channel_state_digest=str(parent.get("channel_state_digest") or ""),
        pricing_state_digest=pricing.pricing_state_digest,
        authority_preflight_digest=str(parent.get("preflight_digest") or ""),
        market_command_plan_digest=plan_digest,
        observation_contract_digest=str(observation_contract["observation_contract_digest"]),
        campaign_id=str(campaign.get("campaign_id") or ""),
        buyer_segment_id=str(ref.get("buyer_segment_id") or ""),
        channel_id=str(ref.get("channel_id") or ""),
        offer_id=str(ref.get("offer_id") or ""),
        currency=str(ref.get("currency") or ""),
        price_minor=int(ref.get("price_minor") or 0),
        measurement_window_seconds=int(episode_cfg.get("measurement_window_seconds") or 0),
        release_state=str(episode_cfg.get("release_state") or ""),
        observation_kinds=tuple(row.value for row in MarketObservationKind),
        market_response_observed=False,
        activation_performed=False,
        seraph_operational_gate_executed=False,
        authority_created=False,
        external_effects=False,
    )
    return plan, pricing, observation_contract, {
        "campaign": campaign,
        "policy": policy,
        "market_command_spec": spec,
    }


def _run_phase4(repo_root: Path, work_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    parent = phase3_authority_receipt(repo_root)
    plan, pricing, observation_contract, market = compile_reference_market_episode(
        repo_root,
        work_root=work_root / "episode",
    )
    schema_path = repo_root / EPISODE_SCHEMA_FILE
    schema_valid = False
    if schema_path.is_file():
        schema = _load_json(schema_path)
        schema_valid = (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema.get("$id") == "dio.market_episode_plan.v1"
        )
    campaign = market["campaign"]
    policy = market["policy"]
    lineage = campaign.get("governance", {}).get("source_lineage", {})
    lineage_complete = all(
        str(lineage.get(key) or "").startswith("sha256:")
        for key in (
            "context_digest", "projection_digest", "offer_state_digest", "channel_state_digest",
            "preflight_digest", "pricing_state_digest", "observation_contract_digest",
        )
    )
    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == config.get("required_parent_acceptance")
        and schema_valid
        and plan.product_id == parent.get("reference_product")
        and plan.context_digest == parent.get("context_digest")
        and plan.projection_digest == parent.get("projection_digest")
        and plan.authority_preflight_digest == parent.get("preflight_digest")
        and pricing.evidence_state == PricingEvidenceState.UNTESTED
        and pricing.exposure_count == 0
        and observation_contract.get("no_response_requires_closed_window") is True
        and observation_contract.get("market_response_observed") is False
        and lineage_complete
        and campaign.get("state") == "draft"
        and campaign.get("approval_state") == "pending"
        and campaign.get("publication_state") == "held"
        and int(campaign.get("budget_cap_minor") or 0) == 0
        and policy.get("automatic_spend") == "off"
        and plan.release_state == "HELD_FOR_AUTHORITY"
        and plan.market_response_observed is False
        and plan.activation_performed is False
        and plan.seraph_operational_gate_executed is False
        and plan.authority_created is False
        and plan.external_effects is False
    )
    return {
        "phase": "M2-4",
        "acceptance": M2_PHASE4_EXIT_TOKEN if passed else "DIO_M2_MARKET_EPISODE_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": plan.product_id,
        "episode_id": plan.episode_id,
        "episode_plan_digest": plan.plan_digest,
        "episode_schema_valid": schema_valid,
        "context_digest": plan.context_digest,
        "projection_digest": plan.projection_digest,
        "offer_state_digest": plan.offer_state_digest,
        "channel_state_digest": plan.channel_state_digest,
        "pricing_state_digest": plan.pricing_state_digest,
        "pricing_evidence_state": pricing.evidence_state.value,
        "price_minor": pricing.amount_minor,
        "currency": pricing.currency,
        "authority_preflight_digest": plan.authority_preflight_digest,
        "authority_preflight_all_effects_refused": parent.get("all_external_effects_refused") is True,
        "market_command_plan_digest": plan.market_command_plan_digest,
        "market_command_existing_organ_reused": True,
        "market_command_campaign_id": plan.campaign_id,
        "market_command_campaign_state": campaign.get("state"),
        "market_command_approval_state": campaign.get("approval_state"),
        "market_command_publication_state": campaign.get("publication_state"),
        "market_command_budget_cap_minor": campaign.get("budget_cap_minor"),
        "market_command_automatic_spend": policy.get("automatic_spend"),
        "market_command_lineage_complete": lineage_complete,
        "buyer_segment_id": plan.buyer_segment_id,
        "channel_id": plan.channel_id,
        "offer_id": plan.offer_id,
        "measurement_window_seconds": plan.measurement_window_seconds,
        "observation_contract_digest": plan.observation_contract_digest,
        "observation_kind_count": len(plan.observation_kinds),
        "no_response_requires_closed_window": observation_contract.get("no_response_requires_closed_window") is True,
        "market_response_observed": False,
        "payment_observed": False,
        "customer_acceptance_observed": False,
        "willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "release_state": plan.release_state,
        "activation_performed": False,
        "seraph_operational_gate_executed": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


def phase4_market_episode_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase4(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-m2-phase4-") as temp:
        return _run_phase4(root, Path(temp))


__all__ = [
    "DEFAULT_EPISODE_CONFIG",
    "EPISODE_SCHEMA_FILE",
    "M2_PHASE4_EXIT_TOKEN",
    "MarketEpisodeError",
    "MarketEpisodePlan",
    "compile_reference_market_episode",
    "phase4_market_episode_receipt",
]
