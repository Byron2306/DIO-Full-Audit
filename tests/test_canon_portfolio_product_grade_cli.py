from __future__ import annotations

import json
import sys


def _extension_receipt() -> dict:
    return {
        "schema": "dio.product_grade.canon_extension_gauntlet_receipt.v2",
        "acceptance_token": "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED",
        "extension_count": 15,
        "variants_per_extension": 3,
        "controlled_journey_count": 45,
        "verified_journey_count": 45,
        "refused_journey_count": 0,
        "product_grade_verified_count": 15,
        "product_grade_refuse_count": 0,
        "all_product_grade_verified": True,
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
        "portfolio_fingerprint": "sha256:" + "e" * 64,
    }


def test_portfolio_cli_requires_verified_68x3_receipt(monkeypatch, tmp_path):
    import scripts.run_canon_portfolio_product_grade as runner

    extension_path = tmp_path / "extension.json"
    extension_path.write_text(json.dumps(_extension_receipt()), encoding="utf-8")
    calls: dict[str, object] = {}

    def fake_portfolio(**kwargs):
        calls.update(kwargs)
        return {
            "acceptance_token": runner.PORTFOLIO_VERIFIED_TOKEN,
            "canon_product_count": 68,
            "controlled_journey_count": 204,
            "all_product_grade_verified": True,
        }

    monkeypatch.setattr(runner, "run_canon_portfolio_product_grade", fake_portfolio)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_canon_portfolio_product_grade",
            "--extension-receipt",
            str(extension_path),
            "--output",
            str(tmp_path / "portfolio"),
            "--require-all",
        ],
    )

    assert runner.main() == 0
    assert calls["extension_receipt"] == _extension_receipt()
    assert calls["historical_anchor_path"] == runner.HISTORICAL_ANCHOR_PATH


def test_portfolio_cli_require_all_refuses_baseline(monkeypatch, tmp_path):
    import scripts.run_canon_portfolio_product_grade as runner

    extension_path = tmp_path / "extension.json"
    extension_path.write_text(json.dumps(_extension_receipt()), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "run_canon_portfolio_product_grade",
        lambda **_: {
            "acceptance_token": runner.PORTFOLIO_BASELINE_TOKEN,
            "canon_product_count": 68,
            "controlled_journey_count": 204,
            "all_product_grade_verified": False,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_canon_portfolio_product_grade",
            "--extension-receipt",
            str(extension_path),
            "--output",
            str(tmp_path / "portfolio"),
            "--require-all",
        ],
    )

    assert runner.main() == 2
