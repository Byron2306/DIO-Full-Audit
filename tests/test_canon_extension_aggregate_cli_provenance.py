from __future__ import annotations

import json
import sys


def test_aggregate_cli_consumes_exact_supplied_studio_receipt_without_rerun(monkeypatch, tmp_path):
    import scripts.run_canon_extension_product_grade as runner

    studio_receipt = {
        "schema": "dio.product_grade.portfolio_gauntlet_receipt.v2",
        "acceptance_token": "DIO_PRODUCT_GRADE_VERIFIED",
        "studios": {
            "site_studio": {
                "status": "PRODUCT_GRADE_VERIFIED",
                "receipt_fingerprint": "sha256:" + "a" * 64,
            }
        },
    }
    studio_path = tmp_path / "studio" / "PRODUCT_GRADE_PORTFOLIO_RECEIPT.json"
    studio_path.parent.mkdir(parents=True, exist_ok=True)
    studio_path.write_text(json.dumps(studio_receipt), encoding="utf-8")

    def forbidden_rerun(**_kwargs):
        raise AssertionError("aggregate must not rerun Studio ProductGrade when an upstream receipt is supplied")

    observed: dict[str, object] = {}

    def fake_aggregate(**kwargs):
        observed["studio_receipt"] = kwargs["studio_product_grade_receipt"]
        return {
            "proof_acceptance_token": runner.PROOF_VERIFIED_TOKEN,
            "acceptance_token": runner.VERIFIED_TOKEN,
        }

    monkeypatch.setattr(runner, "run_product_grade_gauntlet", forbidden_rerun)
    monkeypatch.setattr(runner, "run_canon_extension_product_grade_gauntlet", fake_aggregate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_canon_extension_product_grade",
            "--output",
            str(tmp_path / "aggregate"),
            "--studio-receipt",
            str(studio_path),
            "--require-proof",
            "--require-all",
        ],
    )

    assert runner.main() == 0
    assert observed["studio_receipt"] == studio_receipt
