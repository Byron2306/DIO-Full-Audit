import json
from pathlib import Path

import pytest

from adapters.vamp.snapshot_pipeline import _build_vamp_evidex_handoff


ROOT = Path(__file__).resolve().parents[1]

UNIVERSITY = (
    ROOT / "deliverables/vamp_snapshots"
    / "VAMP-GENERIC-UNIVERSITY-PROOF-001"
    / "VAMP_SNAPSHOT.json"
)

PROFESSIONAL = (
    ROOT / "state/professional_evidence"
    / "evidex-unified-20261011-134722"
    / "normal/vamp-performance"
    / "EXECUTION/vamp_snapshot"
    / "PRO-VAMP-PERFORMANCE"
    / "VAMP_SNAPSHOT.json"
)


def load(path):
    if not path.is_file():
        pytest.skip(f"Historical fixture unavailable: {path}")
    return json.loads(path.read_text())


def test_university_accepted_sources_preserved():
    handoff = _build_vamp_evidex_handoff(load(UNIVERSITY))
    accepted = [
        row for row in handoff["source_mappings"]
        if row["decision"] == "accepted"
    ]
    assert len(accepted) == 3
    assert {
        row["evidence_id"] for row in accepted
    } == {"GEN-E01", "GEN-E02", "GEN-E03"}
    assert all(row["source_sha1"] for row in accepted)
    assert handoff["delivery_authorized"] is False


def test_professional_unmapped_sources_are_not_promoted():
    handoff = _build_vamp_evidex_handoff(load(PROFESSIONAL))
    assert not handoff["source_mappings"]
    assert handoff["delivery_authorized"] is False


def test_missing_objective_reference_refuses():
    snapshot = load(UNIVERSITY)
    snapshot["evidence"][0]["mappings"][0]["objective_id"] = "MISSING"
    with pytest.raises(ValueError, match="missing objective"):
        _build_vamp_evidex_handoff(snapshot)


def test_inconsistent_accepted_count_refuses():
    snapshot = load(UNIVERSITY)
    objective = next(
        item for item in snapshot["objectives"]
        if item["objective_id"] == "GEN-TEACH-001"
    )
    objective["accepted_evidence"] = 99
    with pytest.raises(ValueError, match="count mismatch"):
        _build_vamp_evidex_handoff(snapshot)
