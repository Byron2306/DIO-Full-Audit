from __future__ import annotations

import json
from pathlib import Path

from products.assuranceroom_native_pilot import (
    build_assuranceroom_review_inputs,
    enrich_assuranceroom_customer_packet,
)


def _packet(tmp_path: Path) -> dict:
    packet = tmp_path / "packet"
    sources = packet / "SOURCES"
    sources.mkdir(parents=True)
    for name in ("01_customer_context.md", "02_evidence_register.csv", "03_exception_note.md"):
        (sources / name).write_text("customer metadata\n", encoding="utf-8")
    manifest = {
        "files": [
            {"path": f"SOURCES/{name}", "sha256": "placeholder", "bytes": (sources / name).stat().st_size}
            for name in ("01_customer_context.md", "02_evidence_register.csv", "03_exception_note.md")
        ],
        "packet_fingerprint": "sha256:old",
    }
    (packet / "CUSTOMER_PACKET_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    enrich_assuranceroom_customer_packet(packet)
    return {"packet_dir": str(packet)}


def test_assuranceroom_inputs_preserve_two_distinct_gaps(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    inputs = build_assuranceroom_review_inputs(packet)
    assert {row["requirement_key"] for row in inputs["requirements"]} == {"OP-12", "F-19"}
    assert len(inputs["evidence_inputs"]) == 4
    assert len(inputs["issues"]) == 2
    issues = {row["requirement_key"]: row for row in inputs["issues"]}
    assert "April" in issues["OP-12"]["hypothesis"]
    assert "no independent verification record is supplied" in issues["F-19"]["hypothesis"]
    assert inputs["customer_assertions_used_as_self_supporting_evidence"] is False


def test_assuranceroom_enrichment_keeps_ticket_closure_separate_from_verification(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    sources = Path(packet["packet_dir"]) / "SOURCES"
    ticket = (sources / "remediation_ticket_f19.md").read_text(encoding="utf-8")
    signoffs = (sources / "monthly_reconciliation_signoffs.csv").read_text(encoding="utf-8")
    assert "Status: CLOSED" in ticket
    assert "Independent verification attachment: NOT SUPPLIED" in ticket
    assert "no April sign-off supplied" in signoffs
