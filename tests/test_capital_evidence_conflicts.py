from pathlib import Path

from market_capital.census import CapitalCensus
from market_capital.evidence import EvidenceLedger


def test_conflicting_deadlines_are_preserved(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    ledger = EvidenceLedger(census)

    a = ledger.observe(
        "OPP-1",
        "deadline",
        "2026-10-01",
        source_id="SRC-A",
        source_reference="https://a.example/call",
        observed_at="2026-09-10T08:00:00Z",
    )
    b = ledger.observe(
        "OPP-1",
        "deadline",
        "2026-11-01",
        source_id="SRC-B",
        source_reference="https://b.example/call",
        observed_at="2026-09-10T09:00:00Z",
    )

    row_a = ledger.get(a)
    row_b = ledger.get(b)
    assert row_a["conflict_group_id"] == row_b["conflict_group_id"]
    assert row_a["value"] == "2026-10-01"
    assert row_b["value"] == "2026-11-01"
    assert ledger.current_fact("OPP-1", "deadline")["state"] == "CONFLICT"


def test_identical_observations_do_not_create_false_conflict(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    ledger = EvidenceLedger(census)
    ledger.observe("OPP-1", "deadline", "2026-10-01", source_id="SRC-A", source_reference="https://a.example", observed_at="2026-09-10T08:00:00Z")
    ledger.observe("OPP-1", "deadline", "2026-10-01", source_id="SRC-B", source_reference="https://b.example", observed_at="2026-09-10T09:00:00Z")
    fact = ledger.current_fact("OPP-1", "deadline")
    assert fact["state"] == "CONSISTENT"
    assert fact["value"] == "2026-10-01"


def test_model_output_never_displaces_observed_fact(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    ledger = EvidenceLedger(census)
    ledger.observe("ORG-1", "mission", "education", source_id="SRC-A", source_reference="https://a.example", observed_at="2026-09-10T08:00:00Z")
    ledger.observe("ORG-1", "mission", "responsible AI", source_id="ATLAS", source_reference="internal://atlas", observed_at="2026-09-10T09:00:00Z", assertion_class="MODEL_OUTPUT")
    fact = ledger.current_fact("ORG-1", "mission")
    assert fact["state"] == "OBSERVED_WITH_MODEL_DISAGREEMENT"
    assert fact["value"] == "education"
