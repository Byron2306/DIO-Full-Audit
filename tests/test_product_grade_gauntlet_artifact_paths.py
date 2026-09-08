from __future__ import annotations

from pathlib import Path

from products.product_grade_gauntlet import _repo_relative_primary_artifact


def test_studio_primary_artifact_is_promoted_from_studio_relative_to_repo_relative(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    studio_out = root / "state" / "product_grade" / "studio_support" / "site_studio"
    artifact = studio_out / "customer_delivery" / "index.html"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("<!doctype html><html><body>Studio artifact</body></html>\n", encoding="utf-8")

    observed = _repo_relative_primary_artifact(
        root=root,
        studio_out=studio_out,
        receipt_primary_artifact="customer_delivery/index.html",
    )

    assert observed == "state/product_grade/studio_support/site_studio/customer_delivery/index.html"
    assert (root / observed).is_file()
