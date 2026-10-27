from __future__ import annotations

import sys


def test_native_cli_require_all_builds_studio_provenance_and_runs_15x3(monkeypatch, tmp_path):
    import scripts.run_canon_extension_native_product_grade as runner

    studio_receipt = {
        "schema": "dio.product_grade.gauntlet_receipt.v1",
        "studios": {"site_studio": {"status": "PRODUCT_GRADE_VERIFIED"}},
    }
    calls: dict[str, object] = {}

    def fake_studio_gauntlet(**kwargs):
        calls["studio_kwargs"] = kwargs
        return studio_receipt

    def fake_native_batch(**kwargs):
        calls["native_kwargs"] = kwargs
        assert kwargs["studio_product_grade_receipt"] is studio_receipt
        return {
            "acceptance_token": runner.NATIVE_BATCH_VERIFIED_TOKEN,
            "extension_count": 15,
            "variants_per_extension": 3,
            "controlled_journey_count": 45,
            "verified_journey_count": 45,
            "refused_journey_count": 0,
            "product_grade_verified_count": 15,
            "product_grade_refuse_count": 0,
            "all_product_grade_verified": True,
            "target_count": 15,
            "verified_count": 15,
            "refuse_count": 0,
            "all_verified": True,
        }

    monkeypatch.setattr(runner, "run_product_grade_gauntlet", fake_studio_gauntlet)
    monkeypatch.setattr(runner, "run_native_product_grade_batch", fake_native_batch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_canon_extension_native_product_grade",
            "--output",
            str(tmp_path / "native"),
            "--require-all",
        ],
    )

    assert runner.main() == 0
    assert calls["studio_kwargs"]["root"] == runner.ROOT
    assert calls["native_kwargs"]["root"] == runner.ROOT


def test_native_cli_require_all_refuses_incomplete_15x3_batch(monkeypatch, tmp_path):
    import scripts.run_canon_extension_native_product_grade as runner

    monkeypatch.setattr(
        runner,
        "run_product_grade_gauntlet",
        lambda **_: {"studios": {}},
    )
    monkeypatch.setattr(
        runner,
        "run_native_product_grade_batch",
        lambda **_: {
            "acceptance_token": runner.NATIVE_BATCH_BASELINE_TOKEN,
            "extension_count": 15,
            "variants_per_extension": 3,
            "controlled_journey_count": 45,
            "verified_journey_count": 44,
            "refused_journey_count": 1,
            "product_grade_verified_count": 14,
            "product_grade_refuse_count": 1,
            "all_product_grade_verified": False,
            "target_count": 15,
            "verified_count": 14,
            "refuse_count": 1,
            "all_verified": False,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_canon_extension_native_product_grade",
            "--output",
            str(tmp_path / "native"),
            "--require-all",
        ],
    )
    assert runner.main() == 2
