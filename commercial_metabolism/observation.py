"""M2 Phase 5 market observation paths.

Exercises positive response, negative response and silence through source-bound
controlled fixtures. The phase reuses Market Command for local measurement
materialisation and BEAST Sensorium for evidence-only episode closure. It proves
the observation paths and their semantic boundaries, not real market exposure,
customer acceptance, willingness to pay, commercial validation or repeatability.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from adapters.sensorium.commercial_episode import (
    close_commercial_episode,
    create_commercial_runtime,
    observe_commercial_event,
)
from market_command.core import MarketStore
from metamorphic.contracts import digest_payload, require_digest

from .contracts import MarketObservation, MarketObservationKind
from .episode import M2_PHASE4_EXIT_TOKEN, compile_reference_market_episode, phase4_market_episode_receipt


M2_PHASE5_EXIT_TOKEN = "DIO_M2_MARKET_RESPONSE_OBSERVED"
DEFAULT_OBSERVATION_CONFIG = "config/m2_phase5_market_observation.json"
OBSERVATION_EPISODE_SCHEMA_FILE = "schemas/dio.commercial_observation_episode.v1.json"


class CommercialObservationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommercialObservationEpisode:
    scenario_id: str
    outcome_class: str
    episode_plan_digest: str
    context_digest: str
    source_fixture_digest: str
    market_command_measurement_truth_digest: str
    market_observation_digest: str
    sensorium_episode_hash: str
    sensorium_event_ids: tuple[str, ...]
    controlled_fixture: bool = True
    real_market_exposure_observed: bool = False
    payment_verified: bool = False
    customer_acceptance_observed: bool = False
    willingness_to_pay_proved: bool = False
    commercial_validation_proved: bool = False
    product_globally_invalidated: bool = False
    authority_created: bool = False
    external_effects: bool = False
    schema: str = "dio.commercial_observation_episode.v1"

    def __post_init__(self) -> None:
        if self.scenario_id not in {"positive_response", "negative_response", "no_response"}:
            raise ValueError("unsupported controlled observation scenario")
        if self.outcome_class not in {"POSITIVE_RESPONSE", "NEGATIVE_RESPONSE", "NO_RESPONSE"}:
            raise ValueError("unsupported observation outcome class")
        for field_name in (
            "episode_plan_digest",
            "context_digest",
            "source_fixture_digest",
            "market_command_measurement_truth_digest",
            "market_observation_digest",
            "sensorium_episode_hash",
        ):
            require_digest(getattr(self, field_name), field_name=field_name)
        if not self.sensorium_event_ids or any(not str(value).strip() for value in self.sensorium_event_ids):
            raise ValueError("Sensorium event ids are required")
        if self.controlled_fixture is not True or self.real_market_exposure_observed:
            raise ValueError("M2-5 reference proof is controlled-fixture-only")
        if any(
            (
                self.payment_verified,
                self.customer_acceptance_observed,
                self.willingness_to_pay_proved,
                self.commercial_validation_proved,
                self.product_globally_invalidated,
                self.authority_created,
                self.external_effects,
            )
        ):
            raise ValueError("M2-5 observation paths may not overclaim market truth, authority or external effects")

    @property
    def observation_truth_digest(self) -> str:
        """Stable semantic truth excluding volatile local receipt identities."""
        return digest_payload(
            {
                "schema": "dio.m2.commercial_observation_truth.v1",
                "scenario_id": self.scenario_id,
                "outcome_class": self.outcome_class,
                "episode_plan_digest": self.episode_plan_digest,
                "context_digest": self.context_digest,
                "source_fixture_digest": self.source_fixture_digest,
                "market_command_measurement_truth_digest": self.market_command_measurement_truth_digest,
                "market_observation_digest": self.market_observation_digest,
                "controlled_fixture": True,
                "real_market_exposure_observed": False,
            }
        )

    @property
    def episode_evidence_digest(self) -> str:
        return digest_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "scenario_id": self.scenario_id,
            "outcome_class": self.outcome_class,
            "episode_plan_digest": self.episode_plan_digest,
            "context_digest": self.context_digest,
            "source_fixture_digest": self.source_fixture_digest,
            "market_command_measurement_truth_digest": self.market_command_measurement_truth_digest,
            "market_observation_digest": self.market_observation_digest,
            "sensorium_episode_hash": self.sensorium_episode_hash,
            "sensorium_event_ids": list(self.sensorium_event_ids),
            "controlled_fixture": self.controlled_fixture,
            "real_market_exposure_observed": self.real_market_exposure_observed,
            "payment_verified": self.payment_verified,
            "customer_acceptance_observed": self.customer_acceptance_observed,
            "willingness_to_pay_proved": self.willingness_to_pay_proved,
            "commercial_validation_proved": self.commercial_validation_proved,
            "product_globally_invalidated": self.product_globally_invalidated,
            "authority_created": self.authority_created,
            "external_effects": self.external_effects,
            "observation_truth_digest": self.observation_truth_digest,
            "episode_evidence_digest": self.episode_evidence_digest,
        }


def _load_config(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_OBSERVATION_CONFIG
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommercialObservationError(f"cannot load M2-5 observation config: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != "dio.m2.market_observation_config.v1":
        raise CommercialObservationError("unsupported M2-5 observation config")
    scenarios = value.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != 3:
        raise CommercialObservationError("M2-5 requires exactly three controlled scenarios")
    ids = {str(row.get("scenario_id") or "") for row in scenarios if isinstance(row, dict)}
    if ids != {"positive_response", "negative_response", "no_response"}:
        raise CommercialObservationError("M2-5 controlled scenarios are incomplete")
    if value.get("real_market_exposure_claimed") is not False or value.get("commercial_validation_claimed") is not False:
        raise CommercialObservationError("controlled observation config may not claim real market validation")
    return value


def _measurement_truth_digest(campaign_id: str, metrics: Mapping[str, Any]) -> str:
    fields = (
        "impressions", "reach", "clicks", "enquiries", "qualified_leads",
        "orders", "paid_orders", "spend_minor", "revenue_minor",
    )
    clean = {key: max(0, int(metrics.get(key) or 0)) for key in fields}
    payload = {
        "schema": "dio.m2.market_command_measurement_truth.v1",
        "campaign_id": campaign_id,
        "metrics": clean,
        "manual_minutes": max(0.0, float(metrics.get("manual_minutes") or 0)),
        "source": str(metrics.get("source") or "controlled_fixture"),
    }
    return digest_payload(payload)


def _build_observation(
    *,
    plan: Any,
    scenario: Mapping[str, Any],
    config_digest: str,
    measurement_truth_digest: str,
) -> MarketObservation:
    base = _load_window(scenario)
    fixture_digest = digest_payload(
        {
            "schema": "dio.m2.source_bound_observation_fixture.v1",
            "config_digest": config_digest,
            "scenario": dict(scenario),
        }
    )
    kind = MarketObservationKind(str(scenario.get("kind") or ""))
    return MarketObservation(
        observation_id=f"OBS-{str(scenario.get('scenario_id') or '').upper()}",
        context_digest=plan.context_digest,
        observed_at=str(scenario.get("observed_at") or ""),
        kind=kind,
        source="source_bound_controlled_fixture",
        source_ref=str(scenario.get("source_ref") or ""),
        window_start=base["start"],
        window_end=base["end"],
        window_closed=bool(scenario.get("window_closed")),
        evidence_refs=(fixture_digest, measurement_truth_digest),
        customer_lineage_id=None,
        payment_lineage_id=None,
    )


def _load_window(scenario: Mapping[str, Any]) -> dict[str, str]:
    window = scenario.get("window")
    if isinstance(window, dict):
        return {"start": str(window.get("start") or ""), "end": str(window.get("end") or "")}
    raise CommercialObservationError("scenario window must be materialised before observation construction")


def _materialise_scenarios(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    base = config.get("base_window") or {}
    start = str(base.get("start") or "")
    end = str(base.get("end") or "")
    if not start or not end:
        raise CommercialObservationError("M2-5 base observation window is required")
    rows: list[dict[str, Any]] = []
    for raw in config.get("scenarios") or []:
        row = dict(raw)
        row["window"] = {"start": start, "end": end}
        rows.append(row)
    return rows


def _store_for(target: Path, episode_cfg: Mapping[str, Any]) -> MarketStore:
    return MarketStore(
        db_path=target / "market_command" / "market.sqlite3",
        event_log=target / "market_command" / "events.jsonl",
        config={
            "max_experiment_budget_minor": 0,
            "default_experiment_window_days": int(episode_cfg.get("market_command_default_experiment_window_days") or 1),
            "require_approved_content_for_activation": False,
        },
    )


def exercise_controlled_observation_scenarios(
    repo_root: str | Path,
    *,
    work_root: str | Path,
) -> tuple[tuple[CommercialObservationEpisode, ...], dict[str, Any]]:
    root = Path(repo_root).resolve()
    target = Path(work_root).resolve()
    target.mkdir(parents=True, exist_ok=True)
    config = _load_config(root)
    parent_gate = phase4_market_episode_receipt(root)
    if parent_gate.get("passed") is not True or parent_gate.get("acceptance") != config.get("required_parent_acceptance"):
        raise CommercialObservationError("M2-4 market episode parent is not verified")

    plan, _pricing, observation_contract, market = compile_reference_market_episode(
        root,
        work_root=target / "episode",
    )
    campaign = market["campaign"]
    if campaign.get("state") != "draft" or campaign.get("publication_state") != "held":
        raise CommercialObservationError("M2-5 controlled observation requires held Market Command planning state")

    episode_cfg = json.loads((root / "config/m2_phase4_market_episode.json").read_text(encoding="utf-8")).get("episode") or {}
    store = _store_for(target / "episode", episode_cfg)
    config_digest = digest_payload(config)
    scenarios = _materialise_scenarios(config)
    results: list[CommercialObservationEpisode] = []
    raw_rows: dict[str, Any] = {}

    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id") or "")
        metrics = dict(scenario.get("metrics") or {})
        measurement_truth = _measurement_truth_digest(plan.campaign_id, metrics)
        measurement_receipt = store.record_measurement(plan.campaign_id, metrics)
        observation = _build_observation(
            plan=plan,
            scenario=scenario,
            config_digest=config_digest,
            measurement_truth_digest=measurement_truth,
        )
        fixture_digest = observation.evidence_refs[0]
        runtime = create_commercial_runtime(root, out_dir=target / "sensorium" / scenario_id)
        mission_id = f"{plan.episode_id}:{scenario_id}"
        event_ids = [
            observe_commercial_event(
                runtime,
                mission_id=mission_id,
                event_type="controlled_market_fixture_admitted",
                payload={
                    "scenario_id": scenario_id,
                    "source_fixture_digest": fixture_digest,
                    "controlled_fixture": True,
                    "real_market_exposure_observed": False,
                },
            ),
            observe_commercial_event(
                runtime,
                mission_id=mission_id,
                event_type="market_command_measurement_materialised",
                payload={
                    "scenario_id": scenario_id,
                    "measurement_id": measurement_receipt["measurement_id"],
                    "measurement_truth_digest": measurement_truth,
                    "source": metrics.get("source"),
                },
            ),
            observe_commercial_event(
                runtime,
                mission_id=mission_id,
                event_type="market_observation_recorded",
                payload={
                    "scenario_id": scenario_id,
                    "outcome_class": scenario.get("outcome_class"),
                    "kind": observation.kind.value,
                    "observation_digest": observation.observation_digest,
                    "window_closed": observation.window_closed,
                },
            ),
        ]
        if observation.kind == MarketObservationKind.NO_RESPONSE:
            event_ids.append(
                observe_commercial_event(
                    runtime,
                    mission_id=mission_id,
                    event_type="measurement_window_closed_without_response",
                    payload={
                        "scenario_id": scenario_id,
                        "window_start": observation.window_start,
                        "window_end": observation.window_end,
                        "no_response_scope": "exact_commercial_context_only",
                    },
                )
            )
        sensorium = close_commercial_episode(
            runtime,
            mission_id=mission_id,
            objective_hash=plan.plan_digest,
            initial_state_hash=plan.context_digest,
            outcome={
                "status": "OBSERVED_CONTROLLED_FIXTURE",
                "scenario_id": scenario_id,
                "outcome_class": str(scenario.get("outcome_class") or ""),
                "observation_digest": observation.observation_digest,
                "controlled_fixture": True,
                "real_market_exposure_observed": False,
                "authority_created": False,
            },
        )
        result = CommercialObservationEpisode(
            scenario_id=scenario_id,
            outcome_class=str(scenario.get("outcome_class") or ""),
            episode_plan_digest=plan.plan_digest,
            context_digest=plan.context_digest,
            source_fixture_digest=fixture_digest,
            market_command_measurement_truth_digest=measurement_truth,
            market_observation_digest=observation.observation_digest,
            sensorium_episode_hash=str(sensorium["sensorium_episode_hash"]),
            sensorium_event_ids=tuple(event_ids),
        )
        results.append(result)
        raw_rows[scenario_id] = {
            "scenario": scenario,
            "measurement_receipt": measurement_receipt,
            "observation": observation.to_dict(),
            "sensorium": sensorium,
        }

    return tuple(results), {
        "parent_gate": parent_gate,
        "plan": plan,
        "observation_contract": observation_contract,
        "campaign": store.get_campaign(plan.campaign_id),
        "aggregate_metrics": store.aggregate_metrics(plan.campaign_id),
        "config_digest": config_digest,
        "rows": raw_rows,
    }


def _run_phase5(repo_root: Path, work_root: Path) -> dict[str, Any]:
    config = _load_config(repo_root)
    episodes, evidence = exercise_controlled_observation_scenarios(repo_root, work_root=work_root)
    parent = evidence["parent_gate"]
    plan = evidence["plan"]
    campaign = evidence["campaign"]
    by_id = {row.scenario_id: row for row in episodes}
    schema_path = repo_root / OBSERVATION_EPISODE_SCHEMA_FILE
    schema_valid = False
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_valid = (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and schema.get("$id") == "dio.commercial_observation_episode.v1"
        )

    controlled_outcomes = {row.outcome_class for row in episodes}
    sensorium_complete = all(row.sensorium_event_ids and row.sensorium_episode_hash.startswith("sha256:") for row in episodes)
    truth_digests_unique = len({row.observation_truth_digest for row in episodes}) == 3
    passed = (
        parent.get("passed") is True
        and parent.get("acceptance") == config.get("required_parent_acceptance")
        and schema_valid
        and len(episodes) == 3
        and set(by_id) == {"positive_response", "negative_response", "no_response"}
        and controlled_outcomes == {"POSITIVE_RESPONSE", "NEGATIVE_RESPONSE", "NO_RESPONSE"}
        and by_id["positive_response"].market_observation_digest.startswith("sha256:")
        and by_id["negative_response"].market_observation_digest.startswith("sha256:")
        and by_id["no_response"].market_observation_digest.startswith("sha256:")
        and evidence["rows"]["no_response"]["observation"]["window_closed"] is True
        and sensorium_complete
        and truth_digests_unique
        and campaign.get("state") == "draft"
        and campaign.get("publication_state") == "held"
        and plan.activation_performed is False
        and plan.seraph_operational_gate_executed is False
        and all(row.controlled_fixture is True for row in episodes)
        and all(row.real_market_exposure_observed is False for row in episodes)
        and all(row.payment_verified is False for row in episodes)
        and all(row.customer_acceptance_observed is False for row in episodes)
        and all(row.willingness_to_pay_proved is False for row in episodes)
        and all(row.commercial_validation_proved is False for row in episodes)
        and all(row.product_globally_invalidated is False for row in episodes)
        and all(row.authority_created is False and row.external_effects is False for row in episodes)
    )
    return {
        "phase": "M2-5",
        "acceptance": M2_PHASE5_EXIT_TOKEN if passed else "DIO_M2_MARKET_RESPONSE_OBSERVATION_BLOCKED",
        "passed": passed,
        "parent_phase": parent.get("phase"),
        "parent_acceptance": parent.get("acceptance"),
        "parent_verified": parent.get("passed") is True,
        "reference_product": plan.product_id,
        "episode_plan_digest": plan.plan_digest,
        "context_digest": plan.context_digest,
        "observation_mode": config.get("observation_mode"),
        "controlled_observation_fixture_count": len(episodes),
        "controlled_outcome_classes": sorted(controlled_outcomes),
        "controlled_market_response_paths_exercised": controlled_outcomes == {"POSITIVE_RESPONSE", "NEGATIVE_RESPONSE", "NO_RESPONSE"},
        "positive_response_observed_in_controlled_fixture": True,
        "negative_response_observed_in_controlled_fixture": True,
        "no_response_observed_in_controlled_fixture": True,
        "no_response_window_closed": evidence["rows"]["no_response"]["observation"]["window_closed"] is True,
        "no_response_scope": "exact_commercial_context_only",
        "sensorium_existing_organ_reused": True,
        "sensorium_episode_count": len(episodes),
        "sensorium_complete": sensorium_complete,
        "market_command_existing_organ_reused": True,
        "market_command_campaign_state": campaign.get("state"),
        "market_command_publication_state": campaign.get("publication_state"),
        "market_command_aggregate_metrics": evidence["aggregate_metrics"],
        "observation_truth_digests_unique": truth_digests_unique,
        "observation_episodes": [row.to_dict() for row in episodes],
        "real_market_exposure_observed": False,
        "real_market_response_observed": False,
        "payment_verified": False,
        "customer_acceptance_observed": False,
        "willingness_to_pay_proved": False,
        "commercial_validation_proved": False,
        "repeatability_proved": False,
        "negative_response_globally_invalidates_product": False,
        "silence_globally_invalidates_product": False,
        "commercial_settlement_performed": False,
        "market_crystal_created": False,
        "activation_performed": False,
        "seraph_operational_gate_executed": False,
        "authority_created": False,
        "authority_widened": False,
        "external_effects": False,
        "new_runtime_engine_created": False,
        "m2_final_verified": False,
    }


def phase5_market_observation_receipt(
    repo_root: str | Path,
    *,
    work_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if work_root is not None:
        target = Path(work_root).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return _run_phase5(root, target)
    with tempfile.TemporaryDirectory(prefix="dio-m2-phase5-") as temp:
        return _run_phase5(root, Path(temp))


__all__ = [
    "CommercialObservationEpisode",
    "CommercialObservationError",
    "DEFAULT_OBSERVATION_CONFIG",
    "M2_PHASE5_EXIT_TOKEN",
    "OBSERVATION_EPISODE_SCHEMA_FILE",
    "exercise_controlled_observation_scenarios",
    "phase5_market_observation_receipt",
]
