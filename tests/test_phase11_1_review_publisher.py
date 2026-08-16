from __future__ import annotations

import json
from pathlib import Path

import pytest

from products.phase11_1_gauntlet import run_phase11_1_gauntlet


ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    import importlib.util
    path = ROOT / "scripts" / "publish_phase11_1_review.py"
    spec = importlib.util.spec_from_file_location("review_publisher", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_review_bundle_verifies_and_redacts_operational_paths(tmp_path: Path) -> None:
    run_phase11_1_gauntlet(output_dir=tmp_path / "gauntlet", root=ROOT)
    module = _load_script()
    bundle = tmp_path / "bundle"
    manifest = module.compile_review_bundle(tmp_path / "gauntlet" / "first", bundle)
    assert manifest["privacy_boundary"] == "PRIVATE_REPOSITORY_REQUIRED"
    assert manifest["external_release"] == "REFUSE" and manifest["human_review"] == "NEEDS_YOU"
    assert manifest["include_originals"] is False
    attachment = json.loads((bundle / "VESPER_ATTACHMENT_RECEIPT.json").read_text())
    assert all("/" not in row["quarantine_path"] for row in attachment["attachments"])
    assert all(row["extracted_text"].startswith("[WITHHELD") for row in attachment["attachments"])
    outlook = json.loads((bundle / "OUTLOOK_DRAFT_REVIEW.json").read_text())
    assert "to" not in outlook and outlook["sent"] is False and outlook["send_authorized"] is False


def test_tampered_proof_artifact_is_refused(tmp_path: Path) -> None:
    run_phase11_1_gauntlet(output_dir=tmp_path / "gauntlet", root=ROOT)
    module = _load_script()
    run = tmp_path / "gauntlet" / "first"
    (run / "fulfilment" / "proof" / "EVIDENCE_PACK.html").write_text("tampered")
    with pytest.raises(module.ReviewPublishError, match="hash mismatch"):
        module.compile_review_bundle(run, tmp_path / "bundle")
