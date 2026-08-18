from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.studio_harvest import ROOT, StudioHarvestError, build_studio_case, validate_studio_manifest, verify_studio_proof
from products.studio_harvest_gauntlet import run_gauntlet

SITE = Path("config/studio_harvest/site_studio.json")
CORR = Path("config/studio_harvest/professional_correspondence_studio.json")


def test_studio_harvest_gauntlet(tmp_path: Path) -> None:
    result = run_gauntlet(output_dir=tmp_path / "harvest")
    assert result["acceptance_token"] == "DIO_STUDIO_HARVEST_READY"
    assert result["studio_count"] == 2
    assert result["unsafe_promotion_refusal"] == "PASS"
    assert result["new_engine_created"] is False
    for row in result["studios"].values():
        assert row["job_resolution"] == "PASS"
        assert row["vesper_routing"] == "PASS"
        assert row["controlled_artifact_generation"] == "PASS"
        assert row["deterministic_generation"] == "PASS"
        assert row["tamper_detection"] == "PASS"
        assert row["external_send"] == "REFUSE"
        assert row["payment"] == "REFUSE"


def test_site_studio_artifact_contract(tmp_path: Path) -> None:
    result = build_studio_case(manifest_path=SITE, output_dir=tmp_path / "site")
    out = Path(result["output_dir"])
    page = (out / "marketfront/index.html").read_text(encoding="utf-8")
    css = (out / "marketfront/styles.css").read_text(encoding="utf-8")
    js = (out / "marketfront/app.js").read_text(encoding="utf-8")
    assert "research consultancy" in result["manifest"]["job"]["request"].lower()
    assert "CONTROLLED COMPOSITION PROOF" in page
    assert "@media" in css and "grid-template-columns" in css
    assert "fetch(" not in js and "XMLHttpRequest" not in js
    assert "external_send:'REFUSE'" in js
    assert result["route"]["product"] == "site_studio"
    assert result["route"]["intent"] == "intake_request"
    verify_studio_proof(out, result["proof_manifest"])


def test_correspondence_studio_preserves_send_and_commitment_boundary(tmp_path: Path) -> None:
    result = build_studio_case(manifest_path=CORR, output_dir=tmp_path / "corr")
    out = Path(result["output_dir"])
    draft = (out / "correspondence/DRAFT_EMAIL.txt").read_text(encoding="utf-8")
    boundary = json.loads((out / "correspondence/COMMITMENT_BOUNDARY.json").read_text(encoding="utf-8"))
    outlook = json.loads((out / "operations/OUTLOOK_DRAFT.json").read_text(encoding="utf-8"))
    assert "does not amend the invoice" in draft
    assert boundary["admission_authority"] == "REFUSE"
    assert boundary["settlement_authority"] == "REFUSE"
    assert boundary["send_authority"] == "REFUSE"
    assert outlook["state"] == "DRAFT_ONLY"
    assert outlook["external_send"] == "REFUSE"
    assert result["route"]["product"] == "professional_correspondence_studio"
    verify_studio_proof(out, result["proof_manifest"])


def test_missing_organ_refuses(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / SITE).read_text(encoding="utf-8"))
    manifest["required_organs"][0]["source_ref"] = "missing/organ.py"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(StudioHarvestError, match="required organ source missing"):
        build_studio_case(manifest_path=path, output_dir=tmp_path / "bad-out")


def test_unsafe_authority_refuses() -> None:
    manifest = json.loads((ROOT / CORR).read_text(encoding="utf-8"))
    bad = copy.deepcopy(manifest)
    bad["authority"]["external_send"] = "ALLOW"
    with pytest.raises(StudioHarvestError, match="unsafe Studio Harvest authority"):
        validate_studio_manifest(bad)
