from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .commercial_phoenix import emit_market_observation_v2


def import_legacy_hivenance(value: Mapping[str, Any], *, observed_at: datetime) -> dict[str, Any]:
    """Project historical Hivenance data without allowing it to originate market truth."""
    raw_time = value.get("event_time") or value.get("generated_at") or value.get("observed_at")
    event_time = None
    if raw_time:
        try:
            parsed = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                event_time = parsed
        except ValueError:
            pass
    lineage = value.get("source_lineage") or value.get("source") or {}
    if not isinstance(lineage, Mapping):
        lineage = {}
    source_ref = lineage.get("source_ref") or lineage.get("url") or "legacy://hivenance/unknown"
    row = emit_market_observation_v2(
        observation_id=str(value.get("observation_id") or value.get("id") or "LEGACY-HIVENANCE"),
        source_lineage={**dict(lineage), "source_ref": source_ref, "legacy_import": True},
        event_time=event_time or observed_at,
        triune_assessments=dict(value.get("triune_assessments") or {}),
        payload={},
    )
    row.update({
        "producer": "legacy_hivenance_import",
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_uncertain": event_time is None,
        "legacy_payload": dict(value),
        "legacy_import_only": True,
        "new_market_action_allowed": False,
    })
    return row
