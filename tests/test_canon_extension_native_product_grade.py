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
    "contract-desk",
    "corporate-readiness",
    "entrepreneurproof",
    "finance-readiness",
    "fundingfinder",
    "investorproof",
    "launch-studio",
    "popia-readiness",
    "professional-correspondence",
    "report-pitch-studio",
}


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


def _seed_legacy_canon(root: Path, slug: str) -> tuple[Path, Path]:
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


def _seed_canon(root: Path, slug: str) -> tuple[Path, Path]:
    _, _, seal = _seed_materialization(root, slug)
    return seal.parent / "index.html", seal


def test_native_profile_registry_covers_exactly_the_eleven_receipt_bound_extensions() -> None:
    assert {row["slug"] for row in NATIVE_CANON_EXTENSION_PROFILES} == EXPECTED_SLUGS
    assert len(NATIVE_CANON_EXTENSION_PROFILES) == 11
    assert {row["family"] for row in NATIVE_CANON_EXTENSION_PROFILES} == {
        "publication_professional",
        "readiness_assurance",
        "opportunity_venture",
        "launch_orchestration",
    }
    assert all(row["baseline_anchor"] != row["mutation_anchor"] for row in NATIVE_CANON_EXTENSION_PROFILES)
    assert all(row["forbidden_claims"] for row in NATIVE_CANON_EXTENSION_PROFILES)


@pytest.mark.parametrize("slug", sorted(EXPECTED_SLUGS))
def test_unseen_fixture_changes_semantic_anchor(slug: str) -> None:
    profile = native_profile(slug)
    baseline = "\n".join(row["text"] for row in build_semantic_rows(profile, profile["baseline"]))
    unseen = "\n".join(row["text"] for row in build_semantic_rows(profile, profile["unseen"]))
    assert profile["baseline_anchor"].casefold() in baseline.casefold()
    assert profile["mutation_anchor"].casefold() in unseen.casefold()
    assert profile["baseline_anchor"].casefold() not in unseen.casefold()
    assert baseline != unseen


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


def test_native_batch_runs_all_eleven_cases(tmp_path: Path) -> None:
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

    assert receipt["target_count"] == 11
    assert receipt["verified_count"] == 11
    assert receipt["refuse_count"] == 0
    assert receipt["all_verified"] is True
    assert receipt["acceptance_token"] == NATIVE_BATCH_VERIFIED_TOKEN
    assert set(receipt["products"]) == EXPECTED_SLUGS
    assert receipt["commercial_validation"] == "UNPROVED"


def test_controlled_execution_renders_supplied_source_without_historical_canon_or_product_grade(tmp_path: Path) -> None:
    from docx import Document
    from products import canon_extension_native_product_grade as native

    execute = getattr(native, "run_controlled_native_case", None)
    assert callable(execute), "source-bound native execution must be usable separately from absent historical canon evidence"
    rows = [
        {"paragraph_id": "C1", "text": "Nala controlled finance review 2026"},
        {"paragraph_id": "C2", "text": "Prepare a document review pack for a supplied vehicle quotation."},
        {"paragraph_id": "C3", "text": "Vehicle quotation Q-861: SUPPLIED"},
        {"paragraph_id": "C4", "text": "Signed current cash-flow schedule: MISSING"},
        {"paragraph_id": "C5", "text": "Human review is required; no financing approval is recorded."},
    ]
    result = execute(slug="finance-readiness", source_rows=rows, title="Nala review", root=Path.cwd(), output_dir=tmp_path / "review", channels=["html", "docx"])
    receipt = result["receipt"]
    assert receipt["status"] == "CONTROLLED_NATIVE_REVIEW_RENDERED"
    assert receipt["canon_provenance"] == "NOT_EVALUATED"
    assert receipt["product_grade"] == "NOT_EVALUATED"
    assert receipt["commercial_validation"] == "UNPROVED"
    assert receipt["external_effects"] is False
    assert receipt["authority_created"] is False
    assert receipt["lingua_semantic_custody"] is True
    assert receipt["beast_mechanical_pass"] is True
    assert {row["channel"] for row in receipt["outputs"]} == {"html", "docx"}
    for row in receipt["outputs"]:
        target = Path(result["output_dir"]) / row["path"]
        text = target.read_text() if row["channel"] == "html" else "\n".join(p.text for p in Document(target).paragraphs)
        assert "Nala controlled finance review 2026" in text
        assert "Vehicle quotation Q-861: SUPPLIED" in text
        assert "Signed current cash-flow schedule: MISSING" in text
        assert "Mhlabeni Solar Services" not in text
        assert row["sha256"] == _sha(target)
    registration = json.loads((tmp_path / "review/LINGUA_REGISTRATION_RECEIPT.json").read_text())
    semantic = json.loads(Path(registration["object_path"]).read_text())
    assert receipt["lingua_object_id"] == semantic["object_id"]
    assert receipt["source_input_sha256"]
    assert not (tmp_path / "review/PRODUCT_GRADE_RECEIPT.json").exists()


def _seed_materialization(root: Path, slug: str) -> tuple[Path, Path, Path]:
    artifact, seal_path = _seed_legacy_canon(root, slug)
    anchor = root / "evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json"
    anchor.parent.mkdir(parents=True, exist_ok=True)
    anchor.write_text('{"test_fixture":"historical lineage anchor"}\n')
    generation = artifact.parent / "CANON_EXTENSION_MATERIALIZATION_RECEIPT.json"
    profile_json = json.dumps(native_profile(slug), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    material = {
        "schema": "dio.canon_extension.materialization_receipt.v1", "status": "PASS",
        "canon_id": "CANON-EXT-" + slug.upper().replace("-", "_"), "slug": slug,
        "primary_artifact": str(artifact.relative_to(root)), "primary_artifact_sha256": _sha(artifact),
        "profile_fingerprint": "sha256:" + hashlib.sha256(profile_json).hexdigest(),
        "historical_anchor": str(anchor.relative_to(root)), "historical_anchor_sha256": _sha(anchor),
        "authority_created": False, "external_effects": False,
    }
    generation.write_text(json.dumps(material))
    seal = json.loads(seal_path.read_text())
    seal.update({"canon_id": "CANON-EXT-" + slug.upper().replace("-", "_"), "primary_artifact": str(artifact.relative_to(root)),
                 "source_generation_receipt": str(generation.relative_to(root)),
                 "source_generation_receipt_schema": material["schema"],
                 "source_generation_receipt_sha256": _sha(generation), "strict_materialization_binding": True})
    seal_path.write_text(json.dumps(seal))
    return generation, anchor, seal_path


@pytest.mark.parametrize("mutation,blocker", [
    ("profile", "canon_materialization_profile_mismatch"),
    ("missing_anchor", "canon_materialization_historical_anchor_missing"),
    ("anchor_hash", "canon_materialization_historical_anchor_hash_mismatch"),
    ("source_hash", "canon_materialization_source_hash_mismatch"),
    ("identity", "canon_materialization_identity_mismatch"),
    ("artifact_hash", "canon_materialization_artifact_mismatch"),
])
def test_native_materialization_checks_full_source_profile_and_anchor_chain(tmp_path: Path, mutation: str, blocker: str) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    generation, anchor, seal_path = _seed_materialization(root, "finance-readiness")
    material = json.loads(generation.read_text())
    if mutation == "profile": material["profile_fingerprint"] = "sha256:" + "0" * 64
    elif mutation == "missing_anchor": anchor.unlink()
    elif mutation == "anchor_hash": material["historical_anchor_sha256"] = "0" * 64
    elif mutation == "identity": material["slug"] = "investorproof"
    elif mutation == "artifact_hash": material["primary_artifact_sha256"] = "0" * 64
    generation.write_text(json.dumps(material))
    seal = json.loads(seal_path.read_text())
    seal["source_generation_receipt_sha256"] = "0" * 64 if mutation == "source_hash" else _sha(generation)
    seal_path.write_text(json.dumps(seal))
    receipt = run_native_product_grade_case(slug="finance-readiness", root=root, output_dir=root / "run", beast_checker=_passing_beast)["receipt"]
    assert receipt["status"] == "PRODUCT_GRADE_REFUSE"
    assert blocker in receipt["critical_blockers"]
    assert not (root / "run/customer_delivery").exists(), "untrusted provenance must refuse before buyer rendering"


def test_native_materialization_accepts_a_matching_current_profile_and_anchor(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _seed_materialization(root, "finance-readiness")
    receipt = run_native_product_grade_case(slug="finance-readiness", root=root, output_dir=root / "run", beast_checker=_passing_beast)["receipt"]
    assert receipt["status"] == "PRODUCT_GRADE_VERIFIED"
    assert receipt.get("canon_provenance_scope") == "MATERIALIZATION_CURRENT_PROFILE_AND_HISTORICAL_ANCHOR_BOUND"


def test_native_legacy_seal_cannot_downgrade_current_profile_provenance_requirements(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _seed_legacy_canon(root, "finance-readiness")
    receipt = run_native_product_grade_case(slug="finance-readiness", root=root, output_dir=root / "run", beast_checker=_passing_beast)["receipt"]
    assert receipt["status"] == "PRODUCT_GRADE_REFUSE"
    assert "canon_materialization_required_for_current_profile" in receipt["critical_blockers"]
    assert receipt["canon_provenance_scope"] == "LEGACY_ARTIFACT_SEAL_ONLY"
    assert not (root / "run/customer_delivery").exists()
