from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _held_pack(tmp_path: Path) -> tuple[Path, dict]:
    pack = tmp_path / "SYNTHETIC_EVIDEX_PACK"
    pack.mkdir()
    (pack / "SOURCE_REVIEW.json").write_text(
        json.dumps(
            {
                "schema": "evidex.source_review.v1",
                "release_authorized": False,
                "human_review_required": True,
                "claims": [
                    {
                        "claim_id": "KPI-001",
                        "claim": "Participants trained: 12",
                        "epistemic_state": "UNVERIFIED",
                        "source_bindings": [
                            {
                                "path": "03_SOURCES/register.txt",
                                "sha256": "a" * 64,
                                "excerpt": "Participants trained: 12; independent verification absent.",
                            }
                        ],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    intake = {
        "client": {"organization": "SYNTHETIC FIXTURE"},
        "pack": {
            "project_name": "Quality Rendering Check",
            "purpose": "Internal evidence review",
            "reporting_period": {"start": "2026-01-01", "end": "2026-08-31"},
        },
    }
    return pack, intake


def test_finish_preserves_human_gate_and_unverified_claims(tmp_path: Path) -> None:
    from products.evidex_studio_finish import finish_evidex_pack

    pack, intake = _held_pack(tmp_path)
    receipt = finish_evidex_pack(pack_dir=pack, intake=intake, source_root=ROOT)

    finish_dir = pack / "05_STUDIO_FINISH"
    stored = json.loads((finish_dir / "EVIDEX_STUDIO_FINISH_RECEIPT.json").read_text(encoding="utf-8"))
    html_output = next(row for row in stored["format_core"]["outputs"] if row["channel"] == "html")
    rendered = (finish_dir / html_output["path"]).read_text(encoding="utf-8")

    assert receipt == stored
    assert stored["schema"] == "dio.evidex_studio_finish.v1"
    assert stored["review_boundary"] == {
        "human_review_required": True,
        "release_authorized": False,
    }
    assert stored["format_core"]["qa_passed"] is True
    assert stored["format_core"]["release_mode"] is False
    assert stored["production_studio"]["customer_artifact_separated_from_proof"] is True
    assert stored["nichefoundry"] == {
        "state": "AVAILABLE_ON_APPROVED_BRAND_REQUEST",
        "executed": False,
    }
    assert stored["external_delivery"] == "REFUSE"
    assert stored["publication"] == "REFUSE"
    assert stored["spend"] == "REFUSE"
    assert stored["authority_created"] is False
    assert "UNVERIFIED" in rendered
    assert "HUMAN REVIEW REQUIRED" in rendered
    assert "Participants trained: 12" in rendered


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"release_authorized": True, "human_review_required": False, "claims": []},
        {"release_authorized": False, "human_review_required": True, "claims": "invalid"},
    ],
)
def test_finish_refuses_missing_or_malformed_source_review(tmp_path: Path, payload: dict | None) -> None:
    from products.evidex_studio_finish import EvidexStudioFinishError, finish_evidex_pack

    pack, intake = _held_pack(tmp_path)
    review = pack / "SOURCE_REVIEW.json"
    if payload is None:
        review.unlink()
    else:
        review.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvidexStudioFinishError):
        finish_evidex_pack(pack_dir=pack, intake=intake, source_root=ROOT)

    assert not (pack / "05_STUDIO_FINISH/EVIDEX_STUDIO_FINISH_RECEIPT.json").exists()
