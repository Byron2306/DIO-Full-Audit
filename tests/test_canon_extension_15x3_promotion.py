from __future__ import annotations

from pathlib import Path

from products.canon_extension_product_grade import (
    CANON_EXTENSIONS,
    PRODUCT_GRADE_REFUSE,
    PRODUCT_GRADE_VERIFIED,
    run_canon_extension_product_grade_gauntlet,
)


STUDIO_SLUGS = {
    "article-publication-studio",
    "finance-readiness-studio",
    "professional-correspondence-studio",
    "site-studio",
}


def _studio_rows() -> dict[str, dict]:
    return {
        spec["studio_id"]: {
            "status": PRODUCT_GRADE_VERIFIED,
            "critical_blockers": [],
            "primary_artifact": f"customer_delivery/{spec['studio_id']}/artifact.html",
            "primary_artifact_sha256": "a" * 64,
            "receipt_fingerprint": "sha256:" + (spec["studio_id"][:1] or "a") * 64,
            "beast_mechanical_pass": True,
            "lingua_semantic_custody": True,
            "unseen_input_generalisation": True,
            "customers_will_pay": "UNPROVED",
            "verified_payment": "UNPROVED",
            "external_effects": False,
            "authority_created": False,
        }
        for spec in CANON_EXTENSIONS
        if spec["proof_kind"] == "studio_product_grade"
    }


def _native_studio_receipt(spec: dict, source: dict, *, verified: int = 3) -> dict:
    variants = {
        name: {
            "variant": name,
            "passed": index < verified,
            "critical_blockers": [] if index < verified else ["forced_variant_failure"],
            "receipt_fingerprint": "sha256:" + str(index + 1) * 64,
            "external_effects": False,
            "authority_created": False,
        }
        for index, name in enumerate(("normal", "messy", "adversarial"))
    }
    return {
        "schema": "dio.product_grade.canon_extension_native.v3",
        "slug": spec["slug"],
        "status": PRODUCT_GRADE_VERIFIED if verified == 3 else PRODUCT_GRADE_REFUSE,
        "critical_blockers": [] if verified == 3 else ["variant_adversarial_refused"],
        "variant_count": 3,
        "verified_variant_count": verified,
        "refused_variant_count": 3 - verified,
        "variants": variants,
        "upstream_studio_id": spec["studio_id"],
        "upstream_studio_product_grade_fingerprint": source["receipt_fingerprint"],
        "upstream_studio_artifact": source["primary_artifact"],
        "upstream_studio_artifact_sha256": source["primary_artifact_sha256"],
        "beast_mechanical_pass": verified == 3,
        "lingua_semantic_custody": verified == 3,
        "unseen_input_generalisation": verified == 3,
        "commercial_validation": "UNPROVED",
        "external_effects": False,
        "authority_created": False,
    }


def _run(tmp_path: Path, native: dict[str, dict] | None = None) -> dict:
    studios = _studio_rows()
    return run_canon_extension_product_grade_gauntlet(
        output_dir=tmp_path / "out",
        root=tmp_path,
        studio_product_grade_receipt={"studios": studios},
        native_product_grade_receipts=native,
    )


def test_verified_studio_provenance_without_native_3x_receipt_refuses_productgrade(tmp_path: Path) -> None:
    receipt = _run(tmp_path)

    for slug in STUDIO_SLUGS:
        row = receipt["extensions"][slug]
        assert row["proof_status"] == "CANON_EXTENSION_PROOF_VERIFIED"
        assert row["status"] == PRODUCT_GRADE_REFUSE
        assert "native_product_grade_not_run" in row["critical_blockers"]

    assert receipt["product_grade_verified_count"] == 0


def test_studio_native_receipt_with_only_two_of_three_variants_refuses(tmp_path: Path) -> None:
    studios = _studio_rows()
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "site-studio")
    native = {
        spec["slug"]: _native_studio_receipt(
            spec,
            studios[spec["studio_id"]],
            verified=2,
        )
    }

    receipt = run_canon_extension_product_grade_gauntlet(
        output_dir=tmp_path / "out",
        root=tmp_path,
        studio_product_grade_receipt={"studios": studios},
        native_product_grade_receipts=native,
    )
    row = receipt["extensions"]["site-studio"]

    assert row["status"] == PRODUCT_GRADE_REFUSE
    assert "native_product_grade_3x_not_verified" in row["critical_blockers"]


def test_studio_promotes_only_when_upstream_provenance_and_native_3x_both_verify(tmp_path: Path) -> None:
    studios = _studio_rows()
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "site-studio")
    native = {
        spec["slug"]: _native_studio_receipt(
            spec,
            studios[spec["studio_id"]],
            verified=3,
        )
    }

    receipt = run_canon_extension_product_grade_gauntlet(
        output_dir=tmp_path / "out",
        root=tmp_path,
        studio_product_grade_receipt={"studios": studios},
        native_product_grade_receipts=native,
    )
    row = receipt["extensions"]["site-studio"]

    assert row["status"] == PRODUCT_GRADE_VERIFIED
    assert row["native_product_grade_schema"] == "dio.product_grade.canon_extension_native.v3"
    assert row["verified_variant_count"] == 3
    assert row["source_studio_product_grade_fingerprint"] == studios[spec["studio_id"]]["receipt_fingerprint"]
    assert row["critical_blockers"] == []
