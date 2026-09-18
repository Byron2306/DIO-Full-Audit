from __future__ import annotations

import json
from pathlib import Path

from presence_core.phase7_golden_journey import run_golden_journey_from_artifacts
from products.obligationfamily.runner import FAMILY_DEFINITIONS, run_family_proof


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-18T00:00:00+00:00"


def test_real_obligation_family_runner_can_be_sealed_as_current_phase7_execution(tmp_path: Path) -> None:
    product_id = "dio_grantproof"
    definition = FAMILY_DEFINITIONS[product_id]
    fixture = ROOT / "config" / "products" / "golden" / definition["slug"]
    source = json.loads((fixture / "reference_source.json").read_text(encoding="utf-8"))
    evidence_inputs = json.loads((fixture / "reference_evidence.json").read_text(encoding="utf-8"))["evidence_records"]

    output_dir = tmp_path / "grantproof"
    result = run_family_proof(
        product_id,
        source,
        evidence_inputs,
        output_dir=output_dir,
        operator_id="human.phase7_native_proof",
        now=NOW,
        job_id="phase7-native-obligation-proof",
    )

    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["human_fulfilment_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["waiver_created"] is False
    assert receipt["legal_opinion_created"] is False
    assert receipt["award_or_permit_decision_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False

    paths = sorted(path for path in output_dir.iterdir() if path.is_file())
    assert {path.name for path in paths} == {
        "EVIDENCE_PACK.docx",
        "EVIDENCE_PACK.html",
        "EVIDENCE_PACK.json",
        "EVIDENCE_PACK.pdf",
        "FAMILY_RECEIPT.json",
        "PROOF_MANIFEST.json",
    }

    golden = run_golden_journey_from_artifacts(
        ROOT,
        tmp_path / "journey-state",
        "obligation_assurance",
        artifacts=[
            {
                "artifact_id": f"obligation-{index}",
                "kind": "application/octet-stream",
                "path": path,
            }
            for index, path in enumerate(paths, 1)
        ],
        evidence_refs=[
            f"phase7-native:obligation_assurance:{receipt['case_id']}",
            f"proof-fingerprint:{receipt['proof_fingerprint']}",
        ],
    )
    assert golden["golden_journey_proved"] is True
    assert golden["final_stage"] == "CLOSED"
    assert golden["external_funds_moved"] is False
    assert golden["revenue_recognised"] is False
