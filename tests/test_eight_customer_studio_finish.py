"""Customer evidence offers must execute and prove the existing shared finish."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from products.customer_product_router import run_customer_product


EIGHT_OFFERS = (
    "AuditProof", "QualityProof", "VendorProof", "AssuranceRoom",
    "DiligenceRoom", "DonorProof", "ImpactProof", "ProgrammeProof",
)


def _packet() -> dict:
    requirement = "Each access review must retain a signed completion record."
    observation = "The supplied review register records a late completion."
    return {
        "owner_authorized": True,
        "case_id": "CASE-STUDIO-001",
        "title": "Bounded source review",
        "sources": [
            {"source_id": "RULE", "text": requirement},
            {"source_id": "RECORD", "text": observation},
        ],
        "requirements": [{"requirement_id": "R1", "source_id": "RULE", "quote": requirement}],
        "evidence": [{"source_id": "RECORD", "quote": observation, "supports": ["R1"]}],
        "issues": [{"requirement_id": "R1", "source_id": "RECORD", "quote": observation}],
    }


@pytest.mark.parametrize("product_name", EIGHT_OFFERS)
def test_customer_route_adds_a_real_held_shared_studio_finish(product_name: str, tmp_path: Path) -> None:
    result = run_customer_product(product_name, _packet(), tmp_path, render_pdf=False)
    shared = result["shared_production_finish"]
    assert [r["organ"] for r in shared["organ_steps"]] == ["format_core", "production_studio"]
    assert all(r["state"] == "PASS" for r in shared["organ_steps"])
    assert len(shared["artifacts"]) == 3
    assert all(r["release_state"] == "HELD" for r in shared["artifacts"])

    manifest_file = Path(next(r["path"] for r in shared["artifacts"] if r["mime_type"] == "application/json"))
    manifest = json.loads(manifest_file.read_text())
    assert manifest["schema"] == "dio.production_studio.review_manifest.v2"
    assert manifest["format_core"]["receipt"]["qa"]["passed"] is True
    assert manifest["product_name"] == product_name
    assert manifest["authority_created"] is False
    bound = {r["file_name"]: r["sha256"] for r in manifest["source_artifacts"]}
    assert bound["REVIEW_CONTENT.json"] == hashlib.sha256((tmp_path / "REVIEW_CONTENT.json").read_bytes()).hexdigest()
    assert bound["CUSTOMER_PACKAGE_RECEIPT.json"] == hashlib.sha256((tmp_path / "CUSTOMER_PACKAGE_RECEIPT.json").read_bytes()).hexdigest()

    summary = json.loads((tmp_path / "CUSTOMER_SHARED_FINISH_RECEIPT.json").read_text())
    assert summary["release_authorized"] is False
    assert summary["human_review_required"] is True
    assert result["release_authorized"] is False
    assert any("shared_production_finish/" in a["path"] for a in result["artifacts"])


def test_shared_finish_refuses_tampered_original_customer_document(tmp_path: Path, monkeypatch) -> None:
    from products import customer_specialist_pathways

    original = customer_specialist_pathways.build_evidence_review_package

    def generate_then_corrupt(*args, **kwargs):
        receipt = original(*args, **kwargs)
        html = next((tmp_path / "customer_delivery").glob("*.html"))
        html.write_text("Invented professional approval", encoding="utf-8")
        return receipt

    monkeypatch.setattr(customer_specialist_pathways, "build_evidence_review_package", generate_then_corrupt)
    with pytest.raises(ValueError, match="hash|mismatch|modified"):
        run_customer_product("AuditProof", _packet(), tmp_path, render_pdf=False)
    assert not (tmp_path / "CUSTOMER_EXECUTION_RECEIPT.json").exists()
    assert not list(tmp_path.glob("shared_production_finish/*-production-studio-review-manifest.json"))
