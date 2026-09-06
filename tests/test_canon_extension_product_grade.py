import hashlib
import json
from pathlib import Path

from products.canon_extension_product_grade import (
    BASELINE_TOKEN,
    VERIFIED_TOKEN,
    PROOF_BASELINE_TOKEN,
    PROOF_VERIFIED_TOKEN,
    CANON_EXTENSIONS,
    evaluate_receipt_bound_extension,
    run_canon_extension_product_grade_gauntlet,
)


def _write_receipt_bound_case(root: Path, slug: str, *, mutate=False):
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == slug)
    artifact = root / spec["primary_artifact"]
    receipt = root / spec["proof_receipt"]
    artifact.parent.mkdir(parents=True, exist_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("<html><body><h1>Buyer-facing governed artifact</h1></body></html>\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    receipt.write_text(json.dumps({
        "schema": "fixture.gamma.receipt.v1",
        "status": "PASS",
        "artifact": artifact.name,
        "artifact_sha256": digest,
    }), encoding="utf-8")
    if mutate:
        artifact.write_text(artifact.read_text() + "MUTATED", encoding="utf-8")


def _studio_rows():
    return {
        spec["studio_id"]: {
            "status": "PRODUCT_GRADE_VERIFIED",
            "score": 100,
            "threshold": 85,
            "critical_blockers": [],
            "buyer_grade_candidate": True,
            "primary_artifact": f"customer_delivery/{spec['studio_id']}/artifact.txt",
            "primary_artifact_sha256": "0" * 64,
            "receipt_fingerprint": "sha256:" + "1" * 64,
            "beast_mechanical_pass": True,
            "lingua_semantic_custody": True,
            "legacy_final_copy_used": False,
            "customers_will_pay": "UNPROVED",
            "verified_payment": "UNPROVED",
        }
        for spec in CANON_EXTENSIONS if spec["proof_kind"] == "studio_product_grade"
    }


def test_catalog_has_exactly_15_unique_canon_extensions():
    assert len(CANON_EXTENSIONS) == 15
    assert len({row["canon_id"] for row in CANON_EXTENSIONS}) == 15
    assert len({row["slug"] for row in CANON_EXTENSIONS}) == 15


def test_receipt_bound_artifact_is_proof_verified_but_not_productgrade(tmp_path):
    _write_receipt_bound_case(tmp_path, "contract-desk")
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "contract-desk")
    row = evaluate_receipt_bound_extension(spec=spec, root=tmp_path)
    assert row["proof_status"] == "CANON_EXTENSION_PROOF_VERIFIED"
    assert row["status"] == "PRODUCT_GRADE_REFUSE"
    assert row["artifact_hash_bound"] is True
    assert "native_product_grade_not_run" in row["critical_blockers"]
    assert row["customers_will_pay"] == "UNPROVED"
    assert row["verified_payment"] == "UNPROVED"


def test_mutated_artifact_fails_closed_even_at_receipt_proof_layer(tmp_path):
    _write_receipt_bound_case(tmp_path, "contract-desk", mutate=True)
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "contract-desk")
    row = evaluate_receipt_bound_extension(spec=spec, root=tmp_path)
    assert row["proof_status"] == "CANON_EXTENSION_PROOF_REFUSE"
    assert row["status"] == "PRODUCT_GRADE_REFUSE"
    assert "artifact_not_hash_bound_to_receipt" in row["critical_blockers"]


def test_missing_proof_fails_closed(tmp_path):
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "contract-desk")
    row = evaluate_receipt_bound_extension(spec=spec, root=tmp_path)
    assert row["proof_status"] == "CANON_EXTENSION_PROOF_REFUSE"
    assert row["critical_blockers"]


def test_first_portfolio_run_truthfully_reports_15_proof_candidates_but_only_4_productgrade(tmp_path):
    for spec in CANON_EXTENSIONS:
        if spec["proof_kind"] == "receipt_bound":
            _write_receipt_bound_case(tmp_path, spec["slug"])
    receipt = run_canon_extension_product_grade_gauntlet(
        output_dir=tmp_path / "out",
        root=tmp_path,
        studio_product_grade_receipt={"studios": _studio_rows()},
    )
    assert receipt["acceptance_token"] == BASELINE_TOKEN
    assert receipt["proof_acceptance_token"] == PROOF_VERIFIED_TOKEN
    assert receipt["all_canon_extension_proof_verified"] is True
    assert receipt["extension_count"] == 15
    assert receipt["canon_extension_proof_verified_count"] == 15
    assert receipt["product_grade_verified_count"] == 4
    assert receipt["product_grade_refuse_count"] == 11
    assert receipt["all_product_grade_verified"] is False
    assert receipt["commercial_validation"] == "UNPROVED"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False


def test_explicit_native_productgrade_receipt_can_promote_receipt_bound_extension(tmp_path):
    _write_receipt_bound_case(tmp_path, "contract-desk")
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "contract-desk")
    artifact = tmp_path / spec["primary_artifact"]
    row = evaluate_receipt_bound_extension(
        spec=spec,
        root=tmp_path,
        native_product_grade_receipt={
            "status": "PRODUCT_GRADE_VERIFIED",
            "primary_artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "beast_mechanical_pass": True,
            "lingua_semantic_custody": True,
            "unseen_input_generalisation": True,
            "external_effects": False,
            "authority_created": False,
            "customers_will_pay": "UNPROVED",
            "verified_payment": "UNPROVED",
        },
    )
    assert row["status"] == "PRODUCT_GRADE_VERIFIED"
    assert row["critical_blockers"] == []


def test_native_receipt_with_wrong_artifact_hash_cannot_promote(tmp_path):
    _write_receipt_bound_case(tmp_path, "contract-desk")
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "contract-desk")
    row = evaluate_receipt_bound_extension(
        spec=spec,
        root=tmp_path,
        native_product_grade_receipt={
            "status": "PRODUCT_GRADE_VERIFIED",
            "primary_artifact_sha256": "f" * 64,
            "beast_mechanical_pass": True,
            "lingua_semantic_custody": True,
            "unseen_input_generalisation": True,
            "external_effects": False,
            "authority_created": False,
        },
    )
    assert row["status"] == "PRODUCT_GRADE_REFUSE"
    assert "native_product_grade_artifact_mismatch" in row["critical_blockers"]


def test_portfolio_proof_token_fails_closed_when_one_extension_receipt_is_missing(tmp_path):
    missing_slug = "contract-desk"
    for spec in CANON_EXTENSIONS:
        if spec["proof_kind"] == "receipt_bound" and spec["slug"] != missing_slug:
            _write_receipt_bound_case(tmp_path, spec["slug"])
    receipt = run_canon_extension_product_grade_gauntlet(
        output_dir=tmp_path / "out",
        root=tmp_path,
        studio_product_grade_receipt={"studios": _studio_rows()},
    )
    assert receipt["proof_acceptance_token"] == PROOF_BASELINE_TOKEN
    assert receipt["all_canon_extension_proof_verified"] is False
    assert receipt["canon_extension_proof_verified_count"] == 14


def test_cli_require_proof_succeeds_when_all_extension_proof_is_verified(monkeypatch, tmp_path):
    import sys
    import types

    fake_gauntlet = types.ModuleType("products.product_grade_gauntlet")
    fake_gauntlet.run_product_grade_gauntlet = lambda **_: {"studios": _studio_rows()}
    monkeypatch.setitem(sys.modules, "products.product_grade_gauntlet", fake_gauntlet)
    sys.modules.pop("scripts.run_canon_extension_product_grade", None)
    import scripts.run_canon_extension_product_grade as runner

    monkeypatch.setattr(runner, "run_product_grade_gauntlet", lambda **_: {"studios": _studio_rows()})
    monkeypatch.setattr(
        runner,
        "run_canon_extension_product_grade_gauntlet",
        lambda **_: {
            "acceptance_token": BASELINE_TOKEN,
            "proof_acceptance_token": PROOF_VERIFIED_TOKEN,
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_canon_extension_product_grade",
            "--output",
            str(tmp_path / "out"),
            "--require-proof",
        ],
    )
    assert runner.main() == 0
