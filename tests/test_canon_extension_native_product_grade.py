from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from products.canon_extension_native_profiles import NATIVE_CANON_EXTENSION_PROFILES, native_profile
from products.canon_extension_native_product_grade import (
    NATIVE_BATCH_VERIFIED_TOKEN,
    build_semantic_rows,
    run_native_product_grade_batch,
    run_native_product_grade_case,
)
from products.canon_extension_product_grade import CANON_EXTENSIONS


EXPECTED_SLUGS = {
    "article-publication",
    "article-publication-studio",
    "contract-desk",
    "corporate-readiness",
    "entrepreneurproof",
    "finance-readiness",
    "finance-readiness-studio",
    "fundingfinder",
    "investorproof",
    "launch-studio",
    "popia-readiness",
    "professional-correspondence",
    "professional-correspondence-studio",
    "report-pitch-studio",
    "site-studio",
}

STUDIO_SLUGS = {
    "article-publication-studio",
    "finance-readiness-studio",
    "professional-correspondence-studio",
    "site-studio",
}

VARIANTS = ("normal", "messy", "adversarial")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _passing_beast(*, dio_root: Path, workspace: Path) -> dict:
    assert dio_root.is_dir()
    assert workspace.is_dir()
    assert any(workspace.glob("*.html"))
    return {
        "schema": "dio.beast.product_grade_artifact_checks.v1",
        "mechanical_pass": True,
        "failed_count": 0,
        "checks": [{"name": "html_syntax", "status": "passed"}],
    }


def _messy_failing_beast(*, dio_root: Path, workspace: Path) -> dict:
    failed = "messy" in workspace.parts
    return {
        "schema": "dio.beast.product_grade_artifact_checks.v1",
        "mechanical_pass": not failed,
        "failed_count": 1 if failed else 0,
        "checks": [{"name": "html_syntax", "status": "failed" if failed else "passed"}],
    }


def _seed_canon(root: Path, slug: str) -> tuple[Path, Path]:
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == slug)
    assert spec["proof_kind"] == "receipt_bound"
    artifact = root / spec["primary_artifact"]
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        f"<!doctype html><html><body><h1>{slug}</h1><p>Canonical controlled product surface for {slug}.</p></body></html>\n",
        encoding="utf-8",
    )
    proof = artifact.parent / "CANON_EXTENSION_PROOF_RECEIPT.json"
    proof.write_text(
        json.dumps(
            {
                "schema": "dio.canon_extension.proof_seal.v1",
                "canon_id": spec["canon_id"],
                "slug": slug,
                "status": "PASS",
                "primary_artifact": spec["primary_artifact"],
                "current_artifact_sha256": _sha(artifact),
                "authority_created": False,
                "external_effects": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact, proof


def _studio_receipt(root: Path) -> dict:
    rows: dict[str, dict] = {}
    for spec in CANON_EXTENSIONS:
        if spec["proof_kind"] != "studio_product_grade":
            continue
        studio_id = spec["studio_id"]
        artifact = root / "customer_delivery" / studio_id / "artifact.html"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            f"<!doctype html><html><body><h1>{studio_id}</h1><p>Upstream Studio ProductGrade artifact.</p></body></html>\n",
            encoding="utf-8",
        )
        rows[studio_id] = {
            "status": "PRODUCT_GRADE_VERIFIED",
            "critical_blockers": [],
            "primary_artifact": str(artifact.relative_to(root)),
            "primary_artifact_sha256": _sha(artifact),
            "receipt_fingerprint": "sha256:" + hashlib.sha256(studio_id.encode()).hexdigest(),
            "beast_mechanical_pass": True,
            "lingua_semantic_custody": True,
            "customers_will_pay": "UNPROVED",
            "verified_payment": "UNPROVED",
        }
    return {"studios": rows}


def test_native_profile_registry_covers_exactly_all_fifteen_extensions() -> None:
    assert {row["slug"] for row in NATIVE_CANON_EXTENSION_PROFILES} == EXPECTED_SLUGS
    assert len(NATIVE_CANON_EXTENSION_PROFILES) == 15
    for row in NATIVE_CANON_EXTENSION_PROFILES:
        assert set(row["fixtures"]) == set(VARIANTS)
        assert set(row["anchors"]) == set(VARIANTS)
        assert row["forbidden_claims"]
        assert row["adversarial_pressure"]
        assert row["adversarial_expected_boundary"]


def test_all_four_studio_extensions_have_native_profiles() -> None:
    observed = {row["slug"] for row in NATIVE_CANON_EXTENSION_PROFILES}
    assert STUDIO_SLUGS <= observed


@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_three_fixtures_have_distinct_semantic_anchors(slug: str) -> None:
    profile = native_profile(slug)
    rendered: dict[str, str] = {}
    for variant in VARIANTS:
        fixture = profile["fixtures"][variant]
        rendered[variant] = "\n".join(row["text"] for row in build_semantic_rows(profile, fixture))
        assert profile["anchors"][variant].casefold() in rendered[variant].casefold()
    assert len(set(rendered.values())) == 3
    assert len({profile["anchors"][variant] for variant in VARIANTS}) == 3


@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_adversarial_fixture_declares_pressure_and_boundary(slug: str) -> None:
    profile = native_profile(slug)
    fixture = profile["fixtures"]["adversarial"]
    assert fixture["adversarial_pressure"] == profile["adversarial_pressure"]
    assert profile["adversarial_expected_boundary"]
    assert all(
        claim.casefold() not in profile["adversarial_expected_boundary"].casefold()
        for claim in profile["forbidden_claims"]
    )


def test_native_case_generates_three_isolated_verified_variant_receipts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    canon, proof = _seed_canon(root, "article-publication")
    output = root / "state" / "product_grade" / "canon_extensions" / "article-publication"

    result = run_native_product_grade_case(
        slug="article-publication",
        root=root,
        output_dir=output,
        beast_checker=_passing_beast,
    )
    receipt = result["receipt"]

    assert receipt["schema"] == "dio.product_grade.canon_extension_native.v3"
    assert receipt["status"] == "PRODUCT_GRADE_VERIFIED"
    assert receipt["variant_count"] == 3
    assert receipt["verified_variant_count"] == 3
    assert receipt["refused_variant_count"] == 0
    assert set(receipt["variants"]) == set(VARIANTS)
    assert receipt["canon_artifact_sha256"] == _sha(canon)
    assert receipt["canon_proof_receipt_sha256"] == _sha(proof)
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["commercial_validation"] == "UNPROVED"

    hashes = set()
    for variant in VARIANTS:
        row = receipt["variants"][variant]
        assert row["schema"] == "dio.product_grade.canon_extension_native_variant.v1"
        assert row["variant"] == variant
        assert row["passed"] is True
        assert row["lingua_semantic_custody"] is True
        assert row["beast_mechanical_pass"] is True
        assert row["authority_created"] is False
        assert row["external_effects"] is False
        customer = root / row["customer_artifact"]
        assert customer.is_file()
        assert row["customer_artifact_sha256"] == _sha(customer)
        hashes.add(row["customer_artifact_sha256"])
        variant_receipt = output / "variants" / variant / "PRODUCT_GRADE_VARIANT_RECEIPT.json"
        assert variant_receipt.is_file()
    assert len(hashes) == 3
    assert (output / "PRODUCT_GRADE_RECEIPT.json").is_file()


def test_messy_variant_preserves_ambiguity_in_customer_artifact(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _seed_canon(root, "contract-desk")
    output = root / "state" / "product_grade" / "canon_extensions" / "contract-desk"
    receipt = run_native_product_grade_case(
        slug="contract-desk",
        root=root,
        output_dir=output,
        beast_checker=_passing_beast,
    )["receipt"]
    messy = receipt["variants"]["messy"]
    text = (root / messy["customer_artifact"]).read_text(encoding="utf-8").casefold()
    assert "unsigned pricing schedule" in text
    assert "which schedule version governs" in text
    assert messy["passed"] is True


def test_adversarial_variant_holds_authority_pressure_and_forbidden_claims(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _seed_canon(root, "article-publication")
    output = root / "state" / "product_grade" / "canon_extensions" / "article-publication"
    receipt = run_native_product_grade_case(
        slug="article-publication",
        root=root,
        output_dir=output,
        beast_checker=_passing_beast,
    )["receipt"]
    profile = native_profile("article-publication")
    adversarial = receipt["variants"]["adversarial"]
    text = (root / adversarial["customer_artifact"]).read_text(encoding="utf-8").casefold()
    assert profile["adversarial_expected_boundary"].casefold() in text
    assert adversarial["adversarial_boundary_held"] is True
    assert adversarial["forbidden_claim_hits"] == []
    for forbidden in profile["forbidden_claims"]:
        assert forbidden.casefold() not in text


def test_one_failed_variant_refuses_entire_product(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _seed_canon(root, "contract-desk")
    output = root / "state" / "product_grade" / "canon_extensions" / "contract-desk"
    receipt = run_native_product_grade_case(
        slug="contract-desk",
        root=root,
        output_dir=output,
        beast_checker=_messy_failing_beast,
    )["receipt"]
    assert receipt["status"] == "PRODUCT_GRADE_REFUSE"
    assert receipt["verified_variant_count"] == 2
    assert receipt["refused_variant_count"] == 1
    assert receipt["variants"]["messy"]["passed"] is False
    assert "variant_messy_refused" in receipt["critical_blockers"]


def test_native_case_refuses_when_canon_proof_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _, proof = _seed_canon(root, "popia-readiness")
    proof.unlink()
    output = root / "state" / "product_grade" / "canon_extensions" / "popia-readiness"
    receipt = run_native_product_grade_case(
        slug="popia-readiness",
        root=root,
        output_dir=output,
        beast_checker=_passing_beast,
    )["receipt"]
    assert receipt["status"] == "PRODUCT_GRADE_REFUSE"
    assert "canon_proof_receipt_missing" in receipt["critical_blockers"]
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False


def test_native_batch_requires_all_fifteen_products_and_forty_five_journeys(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    for spec in CANON_EXTENSIONS:
        if spec["proof_kind"] == "receipt_bound":
            _seed_canon(root, spec["slug"])
    output_root = root / "state" / "product_grade" / "canon_extensions"
    receipt = run_native_product_grade_batch(
        root=root,
        output_root=output_root,
        beast_checker=_passing_beast,
        studio_product_grade_receipt=_studio_receipt(root),
    )
    assert NATIVE_BATCH_VERIFIED_TOKEN == "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"
    assert receipt["acceptance_token"] == NATIVE_BATCH_VERIFIED_TOKEN
    assert receipt["extension_count"] == 15
    assert receipt["variants_per_extension"] == 3
    assert receipt["controlled_journey_count"] == 45
    assert receipt["verified_journey_count"] == 45
    assert receipt["refused_journey_count"] == 0
    assert receipt["product_grade_verified_count"] == 15
    assert receipt["product_grade_refuse_count"] == 0
    assert receipt["all_product_grade_verified"] is True
    assert set(receipt["products"]) == EXPECTED_SLUGS
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["commercial_validation"] == "UNPROVED"
