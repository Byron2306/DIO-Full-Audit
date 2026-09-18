from __future__ import annotations

from pathlib import Path

import pytest

from presence_core.customer_cases import load_case
from presence_core.organ_adapter_gauntlet import ORGAN_FAMILIES
from presence_core.phase7_golden_journey import (
    FAMILY_PRODUCTS,
    run_golden_journey_from_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("family_id", list(FAMILY_PRODUCTS))
def test_every_phase7_family_can_close_canonical_golden_journey(
    tmp_path: Path,
    family_id: str,
) -> None:
    artifact = tmp_path / family_id / "fresh-artifact.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        '{"family_id":"' + family_id + '","fresh":true}\n',
        encoding="utf-8",
    )

    binding = ORGAN_FAMILIES[family_id]
    refs = [f"phase7-contract:{family_id}"]
    if binding.get("execution_class") == "external_repo":
        refs.append(
            f"external-repo:{binding['repository']}@{binding['repository_commit']}"
        )

    receipt = run_golden_journey_from_artifacts(
        ROOT,
        tmp_path / "state" / family_id,
        family_id,
        artifacts=[
            {
                "artifact_id": f"{family_id}-fresh-artifact",
                "kind": "application/json",
                "path": artifact,
            }
        ],
        evidence_refs=refs,
    )

    assert receipt["schema"] == "dio.customer_journey.phase7_golden.v1"
    assert receipt["family_id"] == family_id
    assert receipt["representative_product"] == FAMILY_PRODUCTS[family_id]
    assert receipt["settlement_class"] == "CONTROLLED_TEST_SETTLEMENT"
    assert receipt["external_funds_moved"] is False
    assert receipt["revenue_recognised"] is False
    assert receipt["external_network_send"] is False
    assert receipt["golden_journey_proved"] is True
    assert receipt["final_stage"] == "CLOSED"
    assert len(receipt["execution_profile_sha256"]) == 64
    assert len(receipt["fulfilment_request_sha256"]) == 64
    assert len(receipt["fulfilment_result_sha256"]) == 64
    assert len(receipt["manifest_sha256"]) == 64
    assert len(receipt["delivery_receipt_sha256"]) == 64
    assert len(receipt["golden_journey_sha256"]) == 64

    stored = load_case(tmp_path / "state" / family_id, receipt["case_id"])
    assert stored is not None
    assert stored["stage"] == "CLOSED"
    assert stored["settlement"]["settlement_class"] == "CONTROLLED_TEST_SETTLEMENT"
    assert stored["settlement"]["external_funds_moved"] is False
    assert stored["settlement"]["revenue_recognised"] is False
    assert stored["fulfilment"]["release_authority"] is False
    assert stored["fulfilment"]["external_send_authority"] is False
    assert stored["authority_created"] is False
