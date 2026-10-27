from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adapters.hivenance.commercial_phoenix import emit_market_observation_v2
from adapters.hivenance.legacy_import import import_legacy_hivenance


def test_native_commercial_phoenix_observation_preserves_event_and_ingest_time() -> None:
    event_time = datetime(2026, 10, 20, 8, 30, tzinfo=timezone.utc)
    row = emit_market_observation_v2(
        observation_id="OBS-1",
        source_lineage={"source_ref": "https://example.org/public", "sha256": "a" * 64},
        event_time=event_time,
        triune_assessments={"michael": {"score": 0.7}, "loki": {"challenge": "bounded"}, "metatron": {"state": "synthesized"}},
    )

    assert row["schema"] == "dio.market_observation.v2"
    assert row["producer"] == "commercial_phoenix"
    assert row["event_time"] == event_time.isoformat()
    assert row["ingested_at"] != row["event_time"]
    assert row["triune_assessments"]["loki"]["challenge"] == "bounded"


def test_legacy_import_keeps_unknown_fields_and_marks_time_uncertainty() -> None:
    legacy = {
        "observation_id": "LEGACY-1",
        "generated_at": "not-a-time",
        "triune_assessments": {"michael": {"score": 0.5}, "unrecognized": {"detail": "retain"}},
        "source": {"url": "https://example.org/source"},
        "legacy_extension": {"source_system_version": "7.1"},
    }
    row = import_legacy_hivenance(legacy, observed_at=datetime(2026, 10, 27, tzinfo=timezone.utc))

    assert row["producer"] == "legacy_hivenance_import"
    assert row["event_time"] is None
    assert row["event_time_uncertain"] is True
    assert row["triune_assessments"]["unrecognized"] == {"detail": "retain"}
    assert row["legacy_payload"]["legacy_extension"]["source_system_version"] == "7.1"


def test_native_emitter_requires_timezone_aware_event_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        emit_market_observation_v2(
            observation_id="OBS-2",
            source_lineage={"source_ref": "https://example.org"},
            event_time=datetime(2026, 10, 27),
            triune_assessments={},
        )
