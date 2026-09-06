from __future__ import annotations

import sys


def test_native_cli_require_all_succeeds_only_for_verified_batch(monkeypatch, tmp_path):
    import scripts.run_canon_extension_native_product_grade as runner

    monkeypatch.setattr(
        runner,
        "run_native_product_grade_batch",
        lambda **_: {
            "acceptance_token": runner.NATIVE_BATCH_VERIFIED_TOKEN,
            "target_count": 11,
            "verified_count": 11,
            "refuse_count": 0,
            "all_verified": True,
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
    assert runner.main() == 0


def test_native_cli_require_all_refuses_incomplete_batch(monkeypatch, tmp_path):
    import scripts.run_canon_extension_native_product_grade as runner

    monkeypatch.setattr(
        runner,
        "run_native_product_grade_batch",
        lambda **_: {
            "acceptance_token": runner.NATIVE_BATCH_BASELINE_TOKEN,
            "target_count": 11,
            "verified_count": 10,
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
