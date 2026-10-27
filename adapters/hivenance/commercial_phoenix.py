from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Commercial Phoenix event_time must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat()


def emit_market_observation_v2(
    *,
    observation_id: str,
    source_lineage: Mapping[str, Any],
    event_time: datetime,
    triune_assessments: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit native, source-bound market evidence without creating market authority."""
    if not observation_id or not source_lineage.get("source_ref"):
        raise ValueError("Commercial Phoenix observations require observation_id and source lineage.")
    return {
        "schema": "dio.market_observation.v2",
        "observation_id": observation_id,
        "producer": "commercial_phoenix",
        "event_time": _timestamp(event_time),
        "event_time_uncertain": False,
        "ingested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_lineage": dict(source_lineage),
        "triune_assessments": dict(triune_assessments),
        "payload": dict(payload or {}),
        "market_truth_created": False,
        "authority_created": False,
        "external_effects": False,
    }
