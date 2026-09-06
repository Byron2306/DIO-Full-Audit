from __future__ import annotations

import csv
import json
from pathlib import Path

import portfolio_runtime


def _write_crosswalk(path: Path, count: int = 53) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["incarnation", "suite", "primary_family", "source_maturity", "execution_truth_class"],
        )
        writer.writeheader()
        for index in range(count):
            writer.writerow(
                {
                    "incarnation": f"Base Product {index + 1}",
                    "suite": "Historical Base",
                    "primary_family": "Evidence & Assurance",
                    "source_maturity": "Controlled",
                    "execution_truth_class": "CONTROLLED",
                }
            )


def _extension_receipt(*, status: str = "PRODUCT_GRADE_VERIFIED", proof_status: str = "CANON_EXTENSION_PROOF_VERIFIED") -> dict:
    extensions = {}
    for index in range(15):
        slug = f"extension-{index + 1}"
        extensions[slug] = {
            "canon_id": f"CANON-EXT-{index + 1}",
            "name": f"Extension {index + 1}",
            "slug": slug,
            "proof_status": proof_status,
            "status": status,
            "critical_blockers": [],
            "primary_artifact": f"state/product_portfolio/canon_extensions/{slug}/site/index.html",
            "proof_receipt": f"state/product_portfolio/canon_extensions/{slug}/site/CANON_EXTENSION_PROOF_RECEIPT.json",
            "customer_artifact": f"state/product_grade/canon_extensions/{slug}/customer_delivery/index.html",
            "customers_will_pay": "UNPROVED",
            "verified_payment": "UNPROVED",
        }
    return {
        "schema": "dio.product_grade.canon_extension_gauntlet_receipt.v1",
        "acceptance_token": "DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED" if status == "PRODUCT_GRADE_VERIFIED" else "DIO_CANON_EXTENSION_PRODUCT_GRADE_BASELINE_MEASURED",
        "proof_acceptance_token": "DIO_CANON_EXTENSION_PROOF_VERIFIED" if proof_status == "CANON_EXTENSION_PROOF_VERIFIED" else "DIO_CANON_EXTENSION_PROOF_BASELINE_MEASURED",
        "extension_count": 15,
        "product_grade_verified_count": 15 if status == "PRODUCT_GRADE_VERIFIED" else 0,
        "canon_extension_proof_verified_count": 15 if proof_status == "CANON_EXTENSION_PROOF_VERIFIED" else 0,
        "all_product_grade_verified": status == "PRODUCT_GRADE_VERIFIED",
        "all_canon_extension_proof_verified": proof_status == "CANON_EXTENSION_PROOF_VERIFIED",
        "extensions": extensions,
        "commercial_validation": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    crosswalk = tmp_path / "config" / "crosswalk.csv"
    state = tmp_path / "state" / "portfolio.json"
    extension_receipt = tmp_path / "state" / "product_grade" / "canon_extensions" / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
    _write_crosswalk(crosswalk)
    monkeypatch.setattr(portfolio_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(portfolio_runtime, "CROSSWALK", crosswalk)
    monkeypatch.setattr(portfolio_runtime, "STATE_PATH", state)
    monkeypatch.setattr(portfolio_runtime, "EXTENSION_RECEIPT_PATH", extension_receipt)
    return crosswalk, state, extension_receipt


def test_verified_extension_summary_expands_control_deck_portfolio_to_68(monkeypatch, tmp_path):
    _, _, extension_receipt = _configure(monkeypatch, tmp_path)
    extension_receipt.parent.mkdir(parents=True, exist_ok=True)
    extension_receipt.write_text(json.dumps(_extension_receipt()), encoding="utf-8")

    portfolio = portfolio_runtime.import_portfolio()

    assert portfolio["base_canonical_incarnation_count"] == 53
    assert portfolio["canon_extension_count"] == 15
    assert portfolio["canonical_incarnation_count"] == 68
    assert len(portfolio["incarnations"]) == 68
    extension_rows = [row for row in portfolio["incarnations"] if row.get("portfolio_identity") == "canon_extension"]
    assert len(extension_rows) == 15
    assert all(row["Maturity"] == "ProductGrade verified" for row in extension_rows)
    assert all(row["product_grade_status"] == "PRODUCT_GRADE_VERIFIED" for row in extension_rows)
    assert all(row["proof_status"] == "CANON_EXTENSION_PROOF_VERIFIED" for row in extension_rows)
    assert all(row["commercial_validation"] == "UNPROVED" for row in extension_rows)
    assert all(row["authority_created"] is False for row in extension_rows)
    assert all(row["external_effects"] is False for row in extension_rows)
    assert all(row["candidate_product"] is False for row in extension_rows)
    assert all(row["product_package"]["golden_proof_path"].endswith("CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json") for row in extension_rows)


def test_unverified_extension_summary_is_not_promoted_into_canon(monkeypatch, tmp_path):
    _, _, extension_receipt = _configure(monkeypatch, tmp_path)
    extension_receipt.parent.mkdir(parents=True, exist_ok=True)
    extension_receipt.write_text(json.dumps(_extension_receipt(status="PRODUCT_GRADE_REFUSE")), encoding="utf-8")

    portfolio = portfolio_runtime.import_portfolio()

    assert portfolio["canonical_incarnation_count"] == 53
    assert portfolio["canon_extension_count"] == 0
    assert portfolio["extension_summary_state"] == "NOT_VERIFIED"
    assert not [row for row in portfolio["incarnations"] if row.get("portfolio_identity") == "canon_extension"]


def test_portfolio_cache_invalidates_when_extension_summary_changes(monkeypatch, tmp_path):
    _, _, extension_receipt = _configure(monkeypatch, tmp_path)
    extension_receipt.parent.mkdir(parents=True, exist_ok=True)
    extension_receipt.write_text(json.dumps(_extension_receipt()), encoding="utf-8")

    first = portfolio_runtime.import_portfolio()
    assert first["canonical_incarnation_count"] == 68

    extension_receipt.write_text(json.dumps(_extension_receipt(status="PRODUCT_GRADE_REFUSE")), encoding="utf-8")
    second = portfolio_runtime.import_portfolio()

    assert second["canonical_incarnation_count"] == 53
    assert first["source_fingerprint"] != second["source_fingerprint"]
