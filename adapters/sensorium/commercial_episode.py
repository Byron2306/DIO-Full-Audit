from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.sensorium.metamorphic_episode import load_sensorium_runtime_class
from metamorphic.contracts import digest_payload


class CommercialSensoriumError(RuntimeError):
    pass


def create_commercial_runtime(repo_root: str | Path, *, out_dir: str | Path) -> Any:
    Runtime = load_sensorium_runtime_class(repo_root)
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return Runtime(export_root=out / "outbox", boot_id="dio-m2-phase5")


def _canonical_event_type(event_type: str) -> str:
    value = str(event_type or "").strip()
    if not value:
        raise CommercialSensoriumError("commercial Sensorium event type is required")
    if "." not in value:
        value = f"commercial.{value}"
    if not value.startswith("commercial."):
        raise CommercialSensoriumError("commercial Sensorium event types must remain in the commercial.* namespace")
    return value


def observe_commercial_event(
    runtime: Any,
    *,
    mission_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> str:
    receipt = runtime.observe_owned(
        event_type=_canonical_event_type(event_type),
        source="dio_m2_market_observation",
        payload_schema="dio.m2.market_observation_event.v1",
        payload=payload,
        mission_id=mission_id,
        workspace_id="dio-metamorphic-m2",
        confidence_method="source_bound_controlled_fixture",
    )
    event_id = str(receipt.admitted.event.event_id)
    if not event_id:
        raise CommercialSensoriumError("Sensorium admitted commercial event has no identity")
    return event_id


def close_commercial_episode(
    runtime: Any,
    *,
    mission_id: str,
    objective_hash: str,
    initial_state_hash: str,
    outcome: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(outcome, dict):
        raise CommercialSensoriumError("commercial Sensorium outcome must be an object")
    if "effect_hash" in outcome:
        raise CommercialSensoriumError("commercial Sensorium effect_hash is adapter-owned")
    sealed_outcome = dict(outcome)
    sealed_outcome["effect_hash"] = digest_payload(
        {
            "schema": "dio.m2.commercial_sensorium_effect.v1",
            "outcome": outcome,
        }
    )
    episode = runtime.close_episode(
        mission_id,
        objective_hash=objective_hash,
        workspace_identity="dio-metamorphic-m2",
        initial_state_hash=initial_state_hash,
        outcome=sealed_outcome,
        resources={},
        export=False,
    )
    payload = episode.to_dict()
    if payload.get("authority") != "evidence_only":
        raise CommercialSensoriumError("commercial Sensorium episode authority boundary changed")
    payload["sensorium_episode_hash"] = digest_payload(payload)
    return payload


__all__ = [
    "CommercialSensoriumError",
    "close_commercial_episode",
    "create_commercial_runtime",
    "observe_commercial_event",
]
