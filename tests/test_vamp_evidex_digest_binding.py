import json
from pathlib import Path

import pytest

from adapters.vamp.snapshot_pipeline import build_snapshot
from adapters.vamp.evidex_handoff_verifier import (
    HandoffVerificationError,
    verify_handoff,
)


ROOT = Path(__file__).resolve().parents[1]


def test_handoff_digest_and_tamper_refusal(tmp_path):
    source = (
        ROOT
        / "state/professional_evidence"
        / "evidex-unified-20261011-134722"
        / "normal/vamp-performance/PROJECTION"
        / "VAMP_SNAPSHOT_REQUEST.json"
    )

    if not source.is_file():
        pytest.skip("Historical Professional Evidence fixture unavailable")

    output = Path(build_snapshot(source, tmp_path, run_evidex=False))
    snapshot_path = output / "VAMP_SNAPSHOT.json"
    handoff_path = output / "VAMP_EVIDEX_HANDOFF.json"

    receipt = verify_handoff(snapshot_path, handoff_path)

    assert receipt["status"] == "PASS"
    assert receipt["delivery_authorized"] is False

    original = snapshot_path.read_bytes()

    snapshot = json.loads(original)
    snapshot["job_id"] = "TAMPERED"
    snapshot_path.write_text(json.dumps(snapshot))

    with pytest.raises(HandoffVerificationError, match="digest mismatch"):
        verify_handoff(snapshot_path, handoff_path)

    snapshot_path.write_bytes(original)

    handoff = json.loads(handoff_path.read_text())
    handoff["source_mappings"] = []
    handoff_path.write_text(json.dumps(handoff))

    with pytest.raises(HandoffVerificationError, match="handoff content"):
        verify_handoff(snapshot_path, handoff_path)
