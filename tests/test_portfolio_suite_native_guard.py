from __future__ import annotations

import hashlib
from pathlib import Path

from products.native_product_quality import ACCEPTANCE_TOKEN
from products.portfolio_suite_native_guard import SITE_QUALITY_PENDING, apply_native_quality_guard


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(tmp_path: Path, name: str, text: str) -> dict:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return {
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
        "sha256": _hash(path),
    }


def _quality_receipt(tmp_path: Path) -> dict:
    artifacts = {
        "first_exam": _artifact(tmp_path, "first_exam.docx", "exam-one"),
        "first_memo": _artifact(tmp_path, "first_memo.docx", "memo-one"),
        "second_exam": _artifact(tmp_path, "second_exam.docx", "exam-two"),
        "second_memo": _artifact(tmp_path, "second_memo.docx", "memo-two"),
        "customer_source_booklet": _artifact(tmp_path, "CUSTOMER_SOURCE_BOOKLET.md", "source"),
        "review_zip": _artifact(tmp_path, "review.zip", "zip"),
    }
    return {
        "schema": "dio.native_product_quality_receipt.v1",
        "product": "HOMS Exam",
        "native_engine": "scripts.run_hymark_exam_builder.run_builder",
        "artifact_quality_verified": True,
        "site_promotion_allowed": True,
        "surrogate_fallback_allowed": False,
        "authority_created": False,
        "external_effects": False,
        "acceptance_token": ACCEPTANCE_TOKEN,
        "receipt_fingerprint": "sha256:test",
        "artifacts": artifacts,
    }


def _model() -> dict:
    return {
        "schema": "dio.portfolio.suite_surface_model.v1",
        "suite_count": 1,
        "canonical_product_count": 2,
        "suites": [
            {
                "suite_id": "education",
                "name": "Education & Research",
                "suite_state": "ENGINEERING_VERIFIED_NEEDS_SELLABILITY",
                "products": [
                    {
                        "incarnation": "HOMS Exam",
                        "slug": "homs-exam",
                        "category": "buyer_facing_product",
                        "critical_blockers": [],
                        "customer_artifacts": [{"name": "thin.docx"}],
                    },
                    {
                        "incarnation": "HOMS Moderate",
                        "slug": "homs-moderate",
                        "category": "buyer_facing_product",
                        "critical_blockers": [],
                        "customer_artifacts": [{"name": "thin-review.html"}],
                    },
                ],
            }
        ],
        "model_fingerprint": "sha256:old",
    }


def _customer_surface(tmp_path: Path) -> dict:
    thin1 = _artifact(tmp_path, "thin.docx", "thin")
    thin2 = _artifact(tmp_path, "thin-review.html", "thin")
    return {
        "rows": [
            {
                "surface_id": "HOMS Exam",
                "customer_surface_gate": {
                    "selected": [{"name": "thin.docx", **thin1}],
                },
            },
            {
                "surface_id": "HOMS Moderate",
                "customer_surface_gate": {
                    "selected": [{"name": "thin-review.html", **thin2}],
                },
            },
        ]
    }


def test_guard_replaces_thin_homs_artifacts_and_hides_unverified_products(tmp_path: Path) -> None:
    model, customer, guard = apply_native_quality_guard(
        model=_model(),
        customer_surface_receipt=_customer_surface(tmp_path),
        native_quality_receipts=[_quality_receipt(tmp_path)],
    )

    products = {row["incarnation"]: row for row in model["suites"][0]["products"]}
    assert products["HOMS Exam"]["native_artifact_quality_status"] == "VERIFIED"
    assert products["HOMS Moderate"]["native_artifact_quality_status"] == "REFUSE"
    assert SITE_QUALITY_PENDING in products["HOMS Moderate"]["critical_blockers"]
    assert model["suites"][0]["suite_state"] == "REFUSE_SUITE_PRODUCTION"

    rows = {row["surface_id"]: row for row in customer["rows"]}
    homs_selected = rows["HOMS Exam"]["customer_surface_gate"]["selected"]
    moderate_selected = rows["HOMS Moderate"]["customer_surface_gate"]["selected"]
    assert {row["native_artifact_role"] for row in homs_selected} >= {
        "first_exam", "first_memo", "second_exam", "second_memo"
    }
    assert moderate_selected == []
    assert guard["buyer_facing_quality_required_count"] == 2
    assert guard["buyer_facing_quality_verified_count"] == 1
    assert guard["buyer_facing_quality_missing_count"] == 1
    assert guard["site_acceptance_allowed"] is False
