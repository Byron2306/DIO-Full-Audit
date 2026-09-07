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


def _failing_beast(*, dio_root: Path, workspace: Path) -> dict:
    return {
        "schema": "dio.beast.product_grade_artifact_checks.v1",
        "mechanical_pass": False,
        "failed_count": 1,
        "checks": [{"name": "html_syntax", "status": "failed"}],
    }


def _seed_canon(root: Path, slug: str) -> tuple[Path, Path]:
    site = root / "state" / "product_portfolio" / "canon_extensions" / slug / "site"
    site.mkdir(parents=True, exist_ok=True)
    artifact = site / "index.html"
    artifact.write_text(
        f"<!doctype html><html><body><h1>{slug}</h1><p>Canonical controlled product surface for {slug}.</p></body></html>\n",
        encoding="utf-8",
    )
    proof = site / "CANON_EXTENSION_PROOF_RECEIPT.json"
    proof.write_text(
        json.dumps(
            {
                "schema": "dio.canon_extension.proof_seal.v1",
                "slug": slug,
                "status": "PASS",
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


def test_native_case_dual_binds_canon_and_generated_customer_artifact(tmp_path: Path) -> None:
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
    customer = root / receipt["customer_artifact"]

    assert receipt["schema"] == "dio.product_grade.canon_extension_native.v2"
    assert receipt["status"] == "PRODUCT_GRADE_VERIFIED"
    assert receipt["canon_artifact_sha256"] == _sha(canon)
    assert receipt["canon_proof_receipt_sha256"] == _sha(proof)
    assert receipt["customer_artifact_sha256"] == _sha(customer)
    assert receipt["primary_artifact_sha256"] == receipt["customer_artifact_sha256"]
    assert receipt["canon_artifact_sha256"] != receipt["customer_artifact_sha256"]
    assert receipt["lingua_semantic_custody"] is True
    assert receipt["lingua_registration_schema"] == "dio.lingua.product_registration_receipt.v1"
    assert receipt["beast_mechanical_pass"] is True
    assert receipt["unseen_input_generalisation"] is True
    assert receipt["external_effects"] is False
    assert receipt["authority_created"] is False
    assert receipt["commercial_validation"] == "UNPROVED"
    assert (output / "PRODUCT_GRADE_RECEIPT.json").is_file()


def test_native_case_refuses_when_beast_fails(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _seed_canon(root, "contract-desk")
    output = root / "state" / "product_grade" / "canon_extensions" / "contract-desk"

    receipt = run_native_product_grade_case(
        slug="contract-desk",
        root=root,
        output_dir=output,
        beast_checker=_failing_beast,
    )["receipt"]

    assert receipt["status"] == "PRODUCT_GRADE_REFUSE"
    assert "beast_mechanical_failure" in receipt["critical_blockers"]
    assert receipt["beast_mechanical_pass"] is False


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


def test_native_batch_runs_all_fifteen_cases(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    for slug in EXPECTED_SLUGS:
        _seed_canon(root, slug)
    output_root = root / "state" / "product_grade" / "canon_extensions"

    receipt = run_native_product_grade_batch(
        root=root,
        output_root=output_root,
        beast_checker=_passing_beast,
    )

    assert receipt["target_count"] == 15
    assert receipt["verified_count"] == 15
    assert receipt["refuse_count"] == 0
    assert receipt["all_verified"] is True
    assert receipt["acceptance_token"] == NATIVE_BATCH_VERIFIED_TOKEN
    assert set(receipt["products"]) == EXPECTED_SLUGS
    assert receipt["commercial_validation"] == "UNPROVED"
